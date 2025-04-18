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
    __slots__ = ("_dict", "_lower")

    def __init__(app, _dict: dict):
        app._dict = _dict
        app._lower = None

    def _ensure_cache(app):
        if app._lower is None or len(app._lower) != len(app._dict):
            app._lower = {k.lower(): k for k in app._dict}

    def __contains__(app, key):
        app._ensure_cache()
        return key.lower() in app._lower

    def pop(app, key, default=None):
        app._ensure_cache()
        lower_key = key.lower()
        original_key = app._lower.get(lower_key)
        if original_key is not None:
            del app._lower[lower_key]
            return app._dict.pop(original_key)
        return default

if __name__ == "__main__":
    pass
