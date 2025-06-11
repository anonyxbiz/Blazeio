from ..Dependencies import *
from ..Modules.streaming import Context, Abort
from ..Other._refuture import reTask

async def agather(*coros):
    return await gather(*[loop.create_task(coro) if iscoroutine(coro) else coro for coro in coros])

class __Coro__:
    __slots__ = ()
    def __init__(app): pass

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

class DictView:
    __slots__ = ("_dict", "_capitalized",)

    def __init__(app, _dict: dict):
        app._dict = _dict
        app._capitalized = {i.capitalize(): i for i in app._dict}

    def __contains__(app, key):
        if key in app._capitalized:
            return True
        return False

    def __setitem__(app, key, value):
        if key in app._capitalized:
            app.pop(key)
        else:
            app._capitalized[key.capitalize()] = key

        app._dict[key] = value

    def __getitem__(app, key):
        return app._dict[key]

    def get(app, key, default=None):
        return app._dict.get(app._capitalized.get(key), default)

    def pop(app, key, default=None):
        return app._dict.pop(app._capitalized.get(key), default)

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
    __slots__ = ("event", "notify_count", "waiter_count", "_lock_event", "is_locked", "initial")
    def __init__(app, evloop=loop):
        app.event, app._lock_event, app.notify_count, app.waiter_count, app.is_locked, app.initial = SharpEvent(False, evloop), SharpEvent(False, evloop), 0, 0, False, True
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

    async def __aexit__(app, exc_type, exc_value, tb):
        if not app._lock_event.is_set():
            app.release()

    async def __aenter__(app):
        await app.acquire()

    async def acquire(app):
        while app.is_locked:
            await app._lock_event.wait()

        app.lock()

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
            await app.event.wait()

            if app.notify_count:
                app.notify_count -= 1
                break
            elif app.event.is_set() and app.waiter_count:
                app.waiter_count = 0

            app.event.clear()

    async def wait_for(app, predicate: callable):
        while not (result := predicate()):
            await app.wait()

        return result

class Asynchronizer:
    __slots__ = ("jobs", "idle_event", "start_event", "_thread", "loop", "perform_test",)
    def __init__(app, maxsize=0, perform_test=False, await_ready=True):
        app.jobs = asyncQueue(maxsize=maxsize)
        app.perform_test = perform_test
        app.idle_event = SharpEvent()
        app.start_event = SharpEvent()
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
            "event": (event := SharpEvent()),
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
        app.task_activity = SharpEvent(False, app.loop)

        app.task_under_flow = cond(evloop=app.loop)

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

async def traceback_logger(e, *args):
    if isinstance(e, Exception): tb = e.__traceback__
    else: tb = e

    await plog.b_red(str(type(e))[8:-2], *("Exception occured in %s.\nLine: %s.\nfunc: %s.\nCode Part: `%s`.\ntext: %s.\n" % (*extract_tb(tb)[-1], "".join([*args, str(e)]))).split("\n"))

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

    def __init__(app): pass

    def __getattr__(app, name):
        if name in logger.colors._dict:
            def dynamic_method(*args):
                return app.__log__(*args, logger_ = logger.__getattr__(name))

            setattr(app, name, dynamic_method)
            return dynamic_method

        return getattr(logger, name)

    def __log__(app, name: (int, str, None) = None, *logs, sepr = "  ", logger_=None):
        frmt, indent = "", 0

        for log in logs:
            indent += 1
            frmt += "\n%s%s" % (sepr*indent, log)

        if str(name).startswith(app.line_sepr[0]) and (ida := name.find(app.line_sepr[1])) != -1 and (idb := name.find(app.line_sepr[1])) != -1 and (ide := name.find(app.line_sepr[2])) != -1:
            if not (line := app.lines.get(name[:ide + 1])):
                lineno = int(name[idb + len(app.line_sepr[1]):ide])
                app.lines[line] = (line := "\033[%d;1H" % lineno)

            name = name[ide + 1:]
        else:
            line = ""

        return logger_(line + ("<%s[%s]>:%s\n\n" % ("" if name is None else "(%s) -> " % str(name), (now := dt.now(UTC)).strftime("%H:%M:%S:") + str(now.microsecond)[:2], frmt)))

plog = __plog__()

class memarray(bytearray):
    __slots__ = ()
    def __getitem__(app, key):
        if isinstance(key, slice):
            return bytes(memoryview(app)[key])
        return super().__getitem__(key)

    def __setitem__(app, key, value):
        if isinstance(key, slice):
            memoryview(app)[key] = memoryview(value)
            return

        return super().__setitem__(key, value)

if __name__ == "__main__":
    pass
