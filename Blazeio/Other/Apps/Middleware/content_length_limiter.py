# ./Other/Apps/Middleware/content_length_limiter.py
import Blazeio as io

class MaxLength:
    __slots__ = ("parent", "max",)
    def __init__(app, parent, max: int):
        app.parent, app.max = parent, max

    def __call__(app, fn):
        return app.parent.routes(fn, obj = app)

class Length_watch:
    __slots__ = ()
    routes: io.Routemanager = io.Routemanager()
    def __init__(app):
        ...

    def __call__(app, *args, **kwargs):
        return MaxLength(app, *args, **kwargs)

    async def before_middleware(app, r: io.BlazeioProtocol):
        if not (route := app.routes.get(r.path)): return

        if not r.content_length:
            raise io.Abort("Content length is required!", 403)

        if r.content_length > route.nargs[2]["obj"].max:
            raise io.Abort("Payload too large", 413)

if __name__ == "__main__": ...