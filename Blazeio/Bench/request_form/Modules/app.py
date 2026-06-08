# ./Modules/app.py
import Blazeio as io

@io.Scope.web.attach
class APIDocs:
    __slots__ = ()
    def __init__(app):
        ...

    def format_model_form(app, form):
        return {
            "type": form["type"].__name__,
            "model": [
                {
                    key: app.format_form(value)
                    for key, value in form["model"].model.items()
                }
            ]
        }

    def format_form(app, form):
        return {
            "type": form["type"].__name__,
            "model": {
                "default": form.get("default", None),
                "required": False if "default" in form else True
            }
        } if form["type"] != list else app.format_model_form(form)

    async def _api_docs(app, r: io.BlazeioProtocol):
        await io.Deliver.json({i: {
            key: app.format_form(form) for key, form in route.nargs[2]["model"].form.items()
        } for i in io.Scope.web.declared_routes if (route := io.Scope.App.middleware.request_form.routes.get(i))}, indent=4)

@io.Scope.web.attach
class Auth:
    __slots__ = ()
    def __init__(app):
        ...

    @io.Scope.App.middleware.request_form("form", first_name = io.ddict(type = str), last_name = io.ddict(type = str), email = io.ddict(type = str), password = io.ddict(type = str))
    async def _api_auth_register(app, r: io.BlazeioProtocol):
        # r.form.first_name, r.form.last_name, r.form.email, r.form.password are automatically validated, extracted from either url params or request body
        if len(r.form.password) < 10:
            raise io.Abort("Password must be long enough", 403)

        await io.Deliver.text("Ok")

    @io.Scope.App.middleware.request_form("form", email = io.ddict(type = str), password = io.ddict(type = str))
    async def _api_auth_login(app, r: io.BlazeioProtocol):
        await io.Deliver.text("Ok")

@io.Scope.web.attach
class Form:
    __slots__ = ()
    def __init__(app):
        ...

    @io.Scope.App.middleware.request_form(
        "form",
        a = io.ddict(type = int, default = 1),
        b = io.ddict(type = str, default = "b"),
        nested = io.ddict(type = list, model = io.Scope.request_form.Model(
            a = io.ddict(type = int, default = 1),
            b = io.ddict(type = str, default = "b")
        ))
    )
    async def _api_form_nested(app, r: io.BlazeioProtocol):
        await io.Deliver.text("Ok")

    @io.Scope.App.middleware.request_form(
        "form",
        a = io.ddict(type = int, default = 1),
        b = io.ddict(type = str, default = "b"),
        nested = io.ddict(type = list, model = io.Scope.request_form.Model(
            a = io.ddict(type = int, default = 1),
            b = io.ddict(type = str, default = "b"),
            nested = io.ddict(type = list, model = io.Scope.request_form.Model(
                a = io.ddict(type = int, default = 1),
                b = io.ddict(type = str, default = "b")
            ))
        ))
    )
    async def _api_form_nested_deep(app, r: io.BlazeioProtocol):
        await io.Deliver.text("Ok")

if __name__ == "__main__": ...