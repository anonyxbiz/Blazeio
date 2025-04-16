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
    __slots__ = ("_dict",)
    def __init__(app, _dict: dict):
        app._dict = _dict

    def __contains__(app, key):
        for k in app._dict:
            if k.lower() == key.lower():
                return True
        return False

    def pop(app, key, default=None):
        for k in app._dict:
            if k.lower() == key.lower():
                return app._dict.pop(k)
        return default

    def __getattr__(app, name):
        return getattr(app._dict, name)

    def __setattr__(app, key, value):
        if key == "_dict":
            object.__setattr__(app, key, value)
        else:
            app._dict[key] = value

    def __setitem__(app, key, value):
        app._dict[key] = value

    async def find_key(app, key, default=None):
        for k in app._dict:
            if k.lower() == key.lower():
                return k
            await sleep(0)

        return default

    async def items(app):
        for k in app._dict:
            yield (k, app._dict[k])
            await sleep(0)

if __name__ == "__main__":
    pass
