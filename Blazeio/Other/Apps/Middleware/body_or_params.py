# ./Other/Apps/Middleware/body_or_params.py
import Blazeio as io

class BopMiddleware:
    __slots__ = ("key", "routes")
    def __init__(app, key: str):
        app.key, app.routes = key, io.Routemanager()

    @property
    def __name__(app):
        return "BopMiddleware"

    def __call__(app, *args, **kwargs):
        return app.routes.__call__(*args, **kwargs)

    async def before_middleware(app, r: io.BlazeioProtocol):
        if r.path not in app.routes: return
        r.store[app.key] = await r.body_or_params()

if __name__ == "__main__": ...