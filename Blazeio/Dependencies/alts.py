from ..Dependencies import *

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
        if key in app._capitalized: app._dict.pop(app._capitalized[key])
        app._dict[key] = value

    def pop(app, key, default=None):
        return app._dict.pop(app._capitalized.get(key), default)

async def await_for(aw, timeout, _raise=False):
    aw = ensure_future(aw) if not isinstance(aw, asyncio_Future) else aw

    try:
        done, pending = await asyncio_wait(
            {aw},
            timeout=timeout,
            return_when=asyncio_FIRST_COMPLETED
        )

        if not done:
            aw.cancel()
            raise TimeoutError()
        return await next(iter(done))
    except TimeoutError:
        if _raise: raise
        await sleep(0)
    except CancelledError:
        aw.cancel()
        if _raise: raise
        await sleep(0)

class Asynchronizer:
    __slots__ = ("jobs", "idle_event", "_thread", "loop",)

    def __init__(app, maxsize=0):
        app.jobs = asyncQueue(maxsize=maxsize)
        app.idle_event = Event()
        app.idle_event.clear()
        app._thread = Thread(target=app.start, daemon=True)
        app._thread.start()
        app.ready()

    async def job(app, func, *args, **kwargs):
        job = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "exception": None,
            "result": NotImplemented,
            "event": (event := Event())
        }

        event.clear()

        app.loop.call_soon_threadsafe(app.jobs.put_nowait, job)

        await wrap_future(run_coroutine_threadsafe(event.wait(), app.loop))

        if job["exception"]: raise job["exception"]

        return job["result"]

    async def create_task(app, coro):
        return await wrap_future(run_coroutine_threadsafe(coro, app.loop))

    async def worker(app):
        while True:
            job = await app.jobs.get()
            try: job["result"] = job["func"](*job["args"], **job["kwargs"])
            except Exception as e: job["exception"] = e

            job["event"].set()

            if app.jobs.empty(): app.idle_event.set()
            else: app.idle_event.clear()

    async def flush(app):
        return await wrap_future(run_coroutine_threadsafe(app.idle_event.wait(), app.loop))

    def ready(app):
        while not hasattr(app, "loop"):
            timedotsleep(0)

    async def test(app):
        results = [str(result) for result in await gather(*[loop.create_task(app.job(dt.now,)) for i in range(10)])]

        await log.debug(results)

    def start(app):
        app.loop = new_event_loop()
        # loop.create_task(app.test())
        app.loop.run_until_complete(app.worker())

if __name__ == "__main__":
    pass
