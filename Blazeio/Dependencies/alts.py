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

if __name__ == "__main__":
    pass
