# ./Other/Apps/Middleware/request_form.py
import Blazeio as io

class Request:
    __slots__ = ("model", "store_key", "form",)
    def __init__(app, model, store_key: str, **form):
        app.model, app.store_key, app.form = model, store_key, form

    def __call__(app, fn):
        return app.model.routes(fn, model = app)

class RequestModel:
    __slots__ = ()
    routes: io.Routemanager = io.Routemanager()
    def __init__(app):
        ...

    def __call__(app, *args, **kwargs):
        return Request(app, *args, **kwargs)

    async def before_middleware(app, r: io.BlazeioProtocol):
        if not (route := app.routes.get(r.path)): return # O(1) Middleware lookup

        model = route.nargs[2]["model"]
        
        if r.store is None:
            r.store = io.ddict()

        r.store[model.store_key] = io.ddict()

        data = await r.body_or_params()

        for key, form in model.form.items():
            if not (value := data.get(key)) and (value := form.get("default", NotImplemented)) is NotImplemented:
                raise io.Abort("%s is required but its missing" % key, 403)

            try:
                value = form["type"](value)
            except:
                raise io.Abort("%s must be of type (%s)" % (key, str(form["type"])), 403)

            r.store[model.store_key][key] = value

if __name__ == "__main__": ...