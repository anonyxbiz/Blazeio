from ..Dependencies import *
from ..Dependencies import __version__
from ..Dependencies import _getframe
from ..Modules.streaming import Context, Abort
from ..Other._refuture import reTask

@ioConf
def get_func_name(frame: int = 1):
    try:
        caller_frame = _getframe(frame)
        caller_locals = caller_frame.f_locals
        __class__ = None

        for __class__ in caller_locals: break

        if __class__:
            __class__ = caller_locals[__class__].__class__.__name__
        else:
            __class__ = ""

        return "<%s.%s>" % (__class__, caller_frame.f_code.co_name)

    except Exception as e:
        print(e)
        return e.__class__.__name__

async def agather(*coros):
    return await gather(*[loop.create_task(coro) if iscoroutine(coro) else coro for coro in coros])

class __Coro__:
    __slots__ = ()
    def __init__(app): ...

    def __getattr__(app, name):
        if (m := getattr(app, "_%s" % name, None)):
            return m()
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

    async def _method(app):
        return current_task().get_coro().cr_frame.f_code.co_name

    async def task(app):
        return current_task()

Coro = __Coro__()

class SharpEventLab:
    __slots__ = ("_set", "_waiters", "loop", "auto_clear")
    def __init__(app, auto_clear: bool = True, evloop = None):
        app._set, app._waiters, app.loop, app.auto_clear = False, [], evloop or get_event_loop(), auto_clear

    def __repr__(app): return "<%s %s>" % (SharpEventLab.__name__, ", ".join(["(%s=%s)" % (i, str(getattr(app, i, None))) for i in app.__slots__]))

    def is_set(app):
        return app._set
    
    def fut_done(app, fut):
        if fut.__is_cleared__: return
        fut.__is_cleared__ = True
        if app.auto_clear: app.clear()

    def done_callback_orchestrator(app, fut):
        for callback in fut.__acallbacks__:
            callback(fut)

    def add_done_callback(app, callback: callable):
        fut = app.get_fut()
        if callback in fut.__acallbacks__: return
        fut.__acallbacks__.append(callback)

    def get_fut(app):
        if app._waiters:
            return app._waiters[0]

        app._waiters.append(fut := app.loop.create_future())
        fut.__is_cleared__ = False
        fut.__acallbacks__ = [app.fut_done]
        fut.add_done_callback(app.done_callback_orchestrator)

        return fut

    async def wait(app):
        if app._set: return True
        return await app.get_fut()

    def clear(app):
        app._set = False

    def set(app, item = True):
        app._set = True

        if len(app._waiters) == 1:
            if not app._waiters[0].done(): app._waiters[0].set_result(item)
        else:
            for fut in app._waiters:
                if not fut.done(): fut.set_result(item)

        app._waiters.clear()

class ioCondition:
    __slots__ = ("event", "notify_count", "waiter_count", "_lock_event", "is_locked", "initial", "_waiter_event", "_acquire_event", "acquire_waiter_count")
    def __init__(app, evloop=loop, initial=True):
        app.event, app._lock_event, app._waiter_event, app._acquire_event, app.notify_count, app.waiter_count, app.is_locked, app.initial, app.acquire_waiter_count = SharpEvent(evloop = evloop), SharpEvent(evloop = evloop), SharpEvent(evloop = evloop), SharpEvent(evloop = evloop), 0, 0, False, initial, 0
        app.event.set()

    def release(app):
        if app._lock_event.is_set():
            raise RuntimeError("Cannot be invoked on an unlocked lock.")

        app.is_locked = False
        app._lock_event.set()

    def locked(app):
        return app.is_locked

    def lock(app):
        app.is_locked = True
        app._lock_event.clear()

    def notify(app, n: int = 0):
        app.notify_count = n or app.waiter_count
        app.event.set()

    def notify_all(app):
        app.notify()

    def available(app, n: int):
        return int(n - app.waiter_count)

    async def __aexit__(app, exc_type = None, exc_value = None, tb = None):
        if app.locked() or not app._lock_event.is_set():
            app.release()
        return False

    async def __aenter__(app):
        await app.acquire()

    async def acquire(app):
        app.acquire_waiter_count += 1
        app._acquire_event.set()
        while app.locked():
            await app._lock_event.wait_clear()
        app.lock()
        app.acquire_waiter_count -= 1
        app._acquire_event.set()
        return app

    async def wait(app):
        if not app.is_locked:
            raise RuntimeError("Cannot be invoked on an unlocked lock.")
        else:
            app.release()

        if app.initial and app.event.is_set():
            app.initial = False
            return app.event.clear()

        while True:
            app.waiter_count += 1
            app._waiter_event.set()
            await app.event.wait()

            if app.notify_count:
                app.notify_count -= 1
                app.waiter_count -= 1
                app._waiter_event.set()
                break
            elif app.event.is_set() and app.waiter_count:
                app.waiter_count = 0

            app.event.clear()

    async def wait_for(app, predicate: callable):
        while not (result := predicate()):
            await app.wait()

        return result

    async def on_waiter_change(app):
        if not app.is_locked:
            raise RuntimeError("Cannot be invoked on an unlocked lock.")
        else:
            app.release()

        return await app._waiter_event.wait_clear()

    async def on_acquire_change(app):
        return await app._acquire_event.wait_clear()

class Asynchronizer:
    __slots__ = ("jobs", "idle_event", "start_event", "_thread", "loop", "perform_test",)
    def __init__(app, maxsize=0, perform_test=False, await_ready=True):
        app.jobs = asyncQueue(maxsize=maxsize)
        app.perform_test = perform_test
        app.idle_event = SharpEvent(True)
        app.start_event = SharpEvent(True)
        app._thread = Thread(target=app.start, daemon=True)
        app._thread.start()
        if await_ready: loop.run_until_complete(app.ready())

    def is_async(app, func): return iscoroutinefunction(func)

    async def job(app, func, *args, **kwargs):
        job = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "exception": None,
            "result": NotImplemented,
            "event": (event := SharpEvent(True)),
            "loop": get_event_loop(),
            "current_task": current_task()
        }

        app.loop.call_soon_threadsafe(app.jobs.put_nowait, job)

        await wrap_future(run_coroutine_threadsafe(event.wait(), app.loop))

        if job["exception"]:
            if isinstance(job["exception"], Abort): job["exception"].r = await Context.from_task(job["current_task"])

            raise job["exception"]

        return job["result"]

    async def async_tasker(app, job):
        try:
            job["result"] = await job["func"](*job["args"], **job["kwargs"])
        except Exception as e: job["exception"] = e
        finally:
            job["event"].set()

    async def worker(app):
        while True:
            _ = await app.jobs.get()
            while _ or not app.jobs.empty():
                if _:
                    job, _ = _, None
                else:
                    job = app.jobs.get_nowait()

                if not iscoroutinefunction(job["func"]):
                    job["result"] = job["func"](*job["args"], **job["kwargs"])
                    job["event"].set()
                else:
                    app.loop.create_task(app.async_tasker(job))

            if app.jobs.empty(): app.idle_event.set()

    async def flush(app):
        return await wrap_future(run_coroutine_threadsafe(app.idle_event.wait(), app.loop))

    async def ready(app):
        await app.start_event.wait()
    
    async def test_async(app):
        await sleep(0)
        return "Slept"

    async def test(app, i=None, call_type=None, *args, **kwargs):
        calls = 50
        if i is None:
            await wrap_future(run_coroutine_threadsafe(app.ready(), loop))

            await log.debug(dumps(await gather(*[loop.create_task(app.test(i+1, "Asynchronized", dt.now,)) for i in range(calls)]), indent=4))

            await log.debug(dumps(await gather(*[loop.create_task(app.test(i+calls+1, "Direct", dt.now,)) for i in range(calls)]), indent=4))

            return

        if i < calls:
            result = await app.job(*args, **kwargs)
        else:
            if app.is_async(args[0]):
                result = await args[0](*args[1:], **kwargs)
            else:
                result = args[0](*args[1:], **kwargs)

        return "(%s)[%s]: %s" % (call_type, i, str(result))

    def start(app):
        app.loop = new_event_loop()
        loop.call_soon_threadsafe(app.start_event.set,)
        if app.perform_test: loop.create_task(app.test())
        app.loop.run_until_complete(app.worker())

class TaskPool:
    __slots__ = ("taskpool", "task_activity", "task_under_flow", "loop", "maxtasks", "listener_task", "timeout",)
    def __init__(app, maxtasks: int = 100, timeout: (None, float) = None, cond: (Condition, ioCondition) = ioCondition, evloop=loop):
        app.maxtasks, app.timeout, app.taskpool = maxtasks, timeout, []

        app.loop = evloop or get_event_loop()
        app.task_activity = SharpEvent(evloop = app.loop)

        app.task_under_flow = cond(evloop = app.loop)

        app.listener_task = app.loop.create_task(app.listener())

    async def close(app):
        if app.taskpool: await gather(*app.taskpool, return_exceptions=True)

        app.listener_task.cancel()

        try: await app.listener_task
        except CancelledError: pass

    async def gather(app):
        return await gather(*app.taskpool, return_exceptions=True)

    async def listener(app):
        while True:
            await app.task_activity.wait()
            app.task_activity.clear()

            async with app.task_under_flow:
                if int(available := app.maxtasks - len(app.taskpool)) > 0:
                    app.task_under_flow.notify(available)

    def done_callback(app, task):
        if task in app.taskpool: app.taskpool.remove(task)
        app.task_activity.set()

        if task.__taskpool_timer_handle__ and not task.__taskpool_timer_handle__.cancelled():
            task.__taskpool_timer_handle__.cancel()

    def done_callback_orchestrator(app, task):
        for callback in task.__taskpool_callbacks__:
            app.loop.call_soon(callback, task)

    async def add_call_back(app, task, func):
        task.__taskpool_callbacks__.append(func)

    async def create_task(app, *args, **kwargs):
        async with app.task_under_flow:
            app.task_activity.set()
            await app.task_under_flow.wait()

        task = app.loop.create_task(*args, **kwargs)
        app.taskpool.append(task)

        if app.timeout:
            task.__taskpool_timer_handle__ = app.loop.call_later(app.timeout, task.cancel)
        else:
            task.__taskpool_timer_handle__ = app.timeout
        
        task.__taskpool_callbacks__ = [app.done_callback]

        task.__taskpool_add_callback__ = lambda f, t=task: app.add_call_back(t, f)

        task.add_done_callback(app.done_callback_orchestrator)
        return task
    
    def available(app):
        return len(app.taskpool) <= app.maxtasks

class TaskPoolManager:
    __slots__ = ("pool")
    def __init__(app, *args, **kwargs):
        app.pool = TaskPool(*args, **kwargs)

    async def __aenter__(app):
        return app.pool

    async def __aexit__(app, exc_type, exc_value, tb):
        await app.pool.gather()
        await app.pool.close()

class RDict:
    __slots__ = ("_dict",)

    def __init__(app, **kwargs):
        object.__setattr__(app, '_dict', app.convert(kwargs or {}))

    def convert(app, _dict: dict):
        converted = {}
        for key, value in _dict.items():
            if isinstance(value, dict):
                converted[key] = RDict(**value)
            else:
                converted[key] = value
        return converted
    
    def __getattr__(app, name):
        if name == "_dict": return app._dict
        elif name in app._dict:
            return app._dict[name]
        else:
            return getattr(app._dict, name)

    def __contains__(app, key):
        return key in app._dict
    
    def __setitem__(app, key, value):
        if isinstance(value, dict):
            value = RDict(**value)
        app._dict[key] = value
    
    def __setattr__(app, key, value):
        if isinstance(value, dict):
            value = RDict(**value)

        if key in app.__slots__:
            object.__setattr__(app, key, value)
        else:
            app[key] = value

    def __getitem__(app, key):
        if key == "_dict": return app._dict
        return app._dict[key]

    def __repr__(app):
        return repr(app._dict)

create_task = lambda *a, **k: get_event_loop().create_task(*a, **k)

async def traceback_logger(e, *args, frame = 4, frmt_only = False, **kwargs):
    if not (exts := extract_tb(e.__traceback__)):
        try: raise e
        except Exception as e2: e = e2
        finally: exts = extract_tb(e.__traceback__)

    exts = exts[-1]
    
    args = ("Exception occured in %s." % exts[0], "Line: %s." % exts[1], "func: %s." % exts[2], "Code: `%s`." % exts[3], "exc_type: %s" % e.__class__.__name__, "exc_str: %s." % str(e), str(e), *["arg_%d: %s" % (idx+1, str(arg)) for idx, arg in enumerate(args)], *["%s = %s" % (str(key), str(kwargs[key])) for key in kwargs])
    
    if frmt_only: return args

    await plog.b_red(*args, frame = frame)

def read_safe_sync(_type = bytes, *a, **k):
    with open(*a, **k) as fd:
        data = bytearray()

        while (chunk := fd.read(ioConf.INBOUND_CHUNK_SIZE)):
            data.extend(chunk)
            if len(data) >= 100000000:
                raise BlazeioException("File too large")

        if _type == dict:
            return loads(data.decode())
        elif _type == str:
            return data.decode()

        return bytes(data)

class __plog__:
    lines = {"<line_%d>" % i: "\033[%d;1H" % i for i in range(1,2)}

    line_sepr = ("<", "line_", ">")

    __serializer = ioCondition()

    def __init__(app): pass

    def __getattr__(app, name):
        if name in logger.colors._dict:
            def dynamic_method(*args, **kwargs):
                return app.__log__(*args, logger_ = logger.__getattr__(name), **kwargs)

            setattr(app, name, dynamic_method)
            return dynamic_method

        return getattr(logger, name)

    def to_line(app, lineno: int, col: int = 0): return "\033[%d;%dH" % (lineno, col)

    async def __log__(app, name: any = None, *logs, sepr = "  ", logger_: any = None, _format: bool = True, frame: int = 3, func: any = None, dnewline: bool = True, newline: bool = True):
        if not logs:
            logs, name = (name,), None

        if _format and newline:
            sepr0 = "\n"
        else:
            sepr0 = ""

        if dnewline:
            sepr1 = "\n\n"
        else:
            sepr1 = "\n"

        frmt, indent = "", 0
        for log in logs:
            indent += 1
            frmt += "%s%s%s" % (sepr0, sepr*indent, log)

        lineno = None

        if name and str(name).startswith(app.line_sepr[0]) and (ida := str(name).find(app.line_sepr[1])) != -1 and (idb := str(name).find(app.line_sepr[1])) != -1 and (ide := str(name).find(app.line_sepr[2])) != -1:
            name = str(name)
            lineno = int(name[idb + len(app.line_sepr[1]):ide])
            line = app.to_line(lineno)
            name = name[ide + 1:]
        else:
            line = ""

        if _format:
            txt = ("<%s[%s]>:%s%s" % ("(%s%s) -> " % (get_func_name(frame) if func is None else "<%s>" % func.__qualname__ if hasattr(func, "__qualname__") else func.__name__, " - %s" % str(name) if name else ""), (now := dt.now(UTC)).strftime("%H:%M:%S:") + str(now.microsecond)[:2], frmt, sepr1))
        else:
            txt = frmt

        if lineno is not None and (plog_lineno_incr := Taskscope.get("plog_lineno_incr", None)):
            await app.clear_mv(lineno, lineno + int(plog_lineno_incr))

        return await logger_(line + txt)

    async def clear(app, a: int = 0, b: int = 20):
        for line in range(a, b):
            await app.clear_line(line)

    async def clear_line(app, lineno):
        await logger.raw("\033[%d;%dH\x1b[2K" % (lineno, 10))

    async def mvto(app, lineno: int = 1, col: int = 10):
        await logger.raw("\033[%d;%dH" % (lineno, col))

    async def clear_mv(app, a, b):
        await app.clear(a, b)
        await app.mvto(a)
        await logger.flush()
    
    async def clear_and_log(app, _id, *args, **kwargs):
        await app.clear_mv(_id, _id+5)
        return await app.__log__(*args, **kwargs)

plog = __plog__()

class __llog__(__plog__):
    def __getattr__(app, name):
        if name in logger.colors._dict:
            def dynamic_method(*args, **kwargs):
                if not args[0].startswith("<line_"):
                    if (_id := Taskscope.__id__()) is not None and _id < 30:
                        if _id >= 5: _id -= 3

                        return app.clear_and_log(_id, "<line_%d>" % _id, *args, logger_ = logger.__getattr__(name), **kwargs)

                return app.__log__(*args, logger_ = logger.__getattr__(name), **kwargs)

            setattr(app, name, dynamic_method)
            return dynamic_method

        return getattr(logger, name)

llog = __llog__()

class timef:
    @classmethod
    def now(app, *args, **kwargs):
        return (now := dt.now(*args, **kwargs)).strftime("%H:%M:%S:") + str(now.microsecond)[:2]

    @classmethod
    def rnow(app, *args, **kwargs):
        return dt.now(*args, **kwargs)

    @classmethod
    def fnow(app, now):
        return str(now.strftime("%H:%M:%S:")) + str(now.microsecond)[:2]

class Errdetail(BlazeioException):
    __slots__ = (
        'err',
        'time'
    )
    def __init__(app, err):
        app.err = err
        app.time = timef.now()

    def detail(app) -> dict:
        return {"time": app.time, "err": app.err}

    def __str__(app) -> str:
        detail = app.detail()
        try: return dumps(detail, indent=4, escape_forward_slashes=False, reject_bytes=False)
        except: return str(detail)

class Ehandler:
    __slots__ = ("onerr", "ignore", "_raise", "exit_on_err", "err", "on_exit_cbs", "kwargs", "entered", "frame")
    def __init__(app, onerr = None, ignore = [], _raise = [], exit_on_err = False, frame = 5):
        app.kwargs = ddict(onerr=onerr, ignore=ignore, _raise=_raise, exit_on_err=exit_on_err, frame = frame)
        app.entered = False
        app(app.kwargs)

    def __call__(app, kwargs):
        for key in kwargs:
            setattr(app, key, kwargs[key])

        for attr in ("ignore", "_raise"):
            if not isinstance(val := getattr(app, attr), (list, tuple)):
                setattr(app, attr, [val])

        app.err = None
        app.on_exit_cbs = []

    def __enter__(app):
        if app.entered: app(app.kwargs)
        app.entered = True
        return app

    def should_ignore(app, exc_v):
        for ignore in app.ignore:
            if exc_v.__class__.__name__ == ignore.__name__: return True

    def should_raise(app, exc_v):
        for ignore in app._raise:
            if not ignore: return True
            if exc_v.__class__.__name__ == ignore.__name__: return True

    def __exit__(app, exc_t, exc_v, tb):
        if exc_v is not None:
            app.err = exc_v
            if not app.should_ignore(exc_v):
                fut = run_coroutine_threadsafe(traceback_logger(exc_v, frame = app.kwargs.get("frame")), get_event_loop())
                if app.onerr: fut.add_done_callback(lambda fut: app.onerr())

        if app.on_exit_cbs:
            for func, args, kwargs in app.on_exit_cbs:
                func(*args, **kwargs)

        if exc_v is not None:
            if app.should_raise(exc_v): raise exc_v
            if app.exit_on_err: return False
            return True

    def on_exit(app, func, *args, **kwargs):
        app.on_exit_cbs.append((func, args, kwargs))
    
    def add_onerr(app, onerr):
        app.onerr = onerr

    async def __aenter__(app):
        if app.entered: app(app.kwargs)
        app.entered = True
        return app

    async def __aexit__(app, exc_t, exc_v, tb):
        if exc_v is not None:
            app.err = exc_v
            if not app.should_ignore(exc_v):
                await traceback_logger(exc_v, frame = app.kwargs.get("frame"))
                if app.onerr: create_task(app.onerr())
        
        if app.on_exit_cbs:
            for func, args, kwargs in app.on_exit_cbs:
                await func(*args, **kwargs)

        if exc_v is not None:
            if app.exit_on_err: return False
            if app.should_raise(exc_v): return False
            return True

def to_repr(__class__, _type = str):
    if getattr(__class__, "__slots__", None):
        keys = __class__.__slots__

    elif getattr(__class__, "__dict__", None):
        keys = list(__class__.__dict__.keys())

    else:
        keys = list(dir(__class__))

    if _type == str:
        return ", ".join(["(%s = %s)" % (str(key), str(getattr(__class__, key))) for key in keys])
    elif _type == dict:
        return {str(key): str(getattr(__class__, key)) for key in keys}

def perf_timer(start = None):
    if not start:
        start = perf_counter()
    return lambda start = start: perf_counter() - start

async def json_save(filepath: str, json: (bytes, dict, list), mode: str = "wb", *args, **kwargs):
    async with async_open(filepath, mode, *args) as f:
        if isinstance(json, (list, dict)):
            json = dumps(json, **kwargs).encode()

        await f.write(json)

async def json_loads(filepath: str, mode: str = "rb", *args, **kwargs):
    async with async_open(filepath, mode, *args, **kwargs) as f:
        return ddict(loads(await f.read()))

async def aread(filepath: str, *args, **kwargs):
    async with async_open(filepath, "rb", *args, **kwargs) as f:
        return await f.read()

async def asave(filepath: str, data: (bytes, bytearray), *args, **kwargs):
    async with async_open(filepath, "wb", *args, **kwargs) as f:
        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await f.write(data)

class URL:
    __slots__ = ("host", "port", "path", "params", "pathname")
    params_sepr = ("?", "&", "=")
    def __init__(app, url: str, params: (None, dict) = None):
        app.params = {}
        app.host, app.port, app.path = ioConf.url_to_host(url, params or app.params)
        if (idx := app.path.find(app.params_sepr[0])) != -1:
            app.pathname = app.path[:idx]
        else:
            app.pathname = app.path
        app.params = app.get_params(url)

    def get_params(app, url: str):
        prms = ddict()
        if (idx0 := url.find(app.params_sepr[0])) == -1: return prms
        params, idx, idx_end = url[idx0 + 1:], 0, 0

        while idx != -1:
            if (idx := params.find(app.params_sepr[1])) != -1:
                param, params = params[:idx], params[idx+1:]
            else:
                param, params = params, ""

            if (idx := params.find(app.params_sepr[2])) != -1:
                key, value = params[:idx], params[idx + 1:]

                if (idx := value.find(app.params_sepr[1])) != -1:
                    value = value[:idx]
                
                value = ioConf.url_decode_sync(value)

                prms[ioConf.url_decode_sync(key)] = value

        return prms

    def get(app, key = None):
        if not key:
            return {key: getattr(app, key) for key in app.__slots__}
        else:
            return getattr(app, key)

def anydumps(_dict, *args, **kwargs):
    return dumps(ensure_dumpable(_dict), *args, **kwargs)

if __name__ == "__main__": ...
