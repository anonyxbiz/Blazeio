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

if __name__ == "__main__":
    pass
