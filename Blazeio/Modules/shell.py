import Blazeio as io

class Shellposix:
    __slots__ = ("args", "kwargs", "instance")
    def __init__(app, *args, **kwargs):
        app.instance, app.args, app.kwargs = NotImplemented, args, kwargs

    def __getattr__(app, *args):
        return getattr(app.instance, *args)

    async def __aenter__(app):
        app.instance = await io.create_subprocess_shell(*app.args, **app.kwargs)
        return app

    async def __aexit__(app, *args):
        return False

    async def __aiter__(app):
        async for i in app.instance.stdout:
            yield i

create = Shellposix if io.os_name != "nt" else Shellposix

if __name__ == "__main__": ...