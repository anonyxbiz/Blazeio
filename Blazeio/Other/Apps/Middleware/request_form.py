# ./Other/Apps/Middleware/request_form.py
import Blazeio as io

class Model:
    __slots__ = ("model",)
    def __init__(app, **model):
        app.model = model

class RequestDict(io.ddict):
    def sqlize_insert(app, value_type: tuple):
        keys, values = [], []
        for i in app.keys():
            if isinstance(value := app.get(i), value_type):
                keys.append(i)
                values.append(value)

        return (", ".join(keys), ", ".join(["?" for i in range(len(keys))]), values)

    def sqlize_update(app, value_type: tuple):
        keys, values = [], []
        for i in app.keys():
            if isinstance(value := app.get(i), value_type):
                keys.append(i)
                values.append(value)

        return (", ".join(["%s = ?" % key for key in keys]), values)

class Request:
    __slots__ = ("model", "store_key", "form",)
    def __init__(app, model, store_key: str, **form):
        app.model, app.store_key, app.form = model, store_key, form

    def __call__(app, fn):
        return app.model.routes(fn, model = app)

    def construct_form(app, data: dict, model_form: (dict, None) = None):
        form_data = RequestDict()
        
        if not model_form:
            model_form = app.form

        for key, form in model_form.items():
            if not (value := data.get(key)) and (value := form.get("default", NotImplemented)) is NotImplemented:
                raise io.Abort("%s is required but its missing" % key, 403)

            try:
                value = form["type"](value)
            except:
                raise io.Abort("%s must be of type (%s)" % (key, str(form["type"])), 403)

            if form["type"] == list and (m := form.get("model")):
                value = [app.construct_form(i, m.model) for i in value]

            form_data[key] = value

        return form_data

    async def form_data(app, r: io.BlazeioProtocol):
        r.store[app.store_key] = app.construct_form(await r.body_or_params())

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

        await model.form_data(r)

if __name__ == "__main__": ...