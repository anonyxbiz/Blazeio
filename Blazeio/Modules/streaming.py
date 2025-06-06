from ..Dependencies import *
from .reasons import *

class Context:
    @classmethod
    async def r(app):
        return current_task().get_coro().cr_frame.f_locals.get("app")

    @classmethod
    def r_sync(app):
        return current_task().get_coro().cr_frame.f_locals.get("app")

    @classmethod
    async def from_task(app, task):
        return task.get_coro().cr_frame.f_locals.get("app")

class Prepare:
    @classmethod
    async def text(app, headers: dict={}, status:int = 206, content_type: str = "text/plain; charset=utf-8"):
        r = Context.r_sync()
        headers = dict(headers)
        headers["Content-Type"] = content_type

        await r.prepare(headers, status)

    @classmethod
    async def json(app, headers: dict={}, status:int = 206, content_type: str = "application/json; charset=utf-8"):
        r = Context.r_sync()
        headers = dict(headers)
        headers["Content-Type"] = content_type

        await r.prepare(headers, status)

class __Deliver__:
    content_types = {
        "text": "text/plain; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }

    def __init__(app):
        pass

    async def deliver(app, r, data: (str, bytes, bytearray, memoryview, None, dict) = None, status: int = 200, headers: (dict, None) = None, path: (str, None) = None, content_type: (str, None) = None, indent: int = 0):
        headers = headers or {}
        if isinstance(data, str):
            data = data.encode()
        elif isinstance(data, bytearray):
            data = bytes(data)
        elif isinstance(data, memoryview):
            data = bytes(data)
        elif isinstance(data, (dict, list)):
            data = dumps(data, indent=indent).encode()

        headers["Content-type"] = content_type

        if path:
            status = 302 if status == 200 else status
            headers["Location"] = path

        await r.prepare(headers, status)
        await r.write(data)

    def __getattr__(app, name):
        def method(*a, **kw):
            if not isinstance(a[0], BlazeioProtocol):
                a = (Context.r_sync(), *a)

            return app.deliver(*a, **kw, content_type = app.content_types.get(name, name.replace("_", "/")))

        setattr(app, name, method)
        return method

Deliver = __Deliver__()

class Abort(BlazeioException):
    __slots__ = (
        'args',
        'r',
    )

    def __init__(
        app,
        *args
    ):
        app.args = args
        app.r = Context.r_sync()

    def text(app):
        message = (app.args[0] if len(app.args) >= 1 else "Something went wrong").encode()
        status = app.args[1] if len(app.args) >= 2 else 403
        headers = app.args[2] if len(app.args) >= 3 else None

        return Deliver.text(app.r, memoryview(message), status, headers or {})

class Eof(BlazeioException):
    __slots__ = ()
    def __init__(app, *args): pass

class __Payload__:
    __slots__ = ()
    def __init__(app): pass

    def __getattr__(app, name):
        return getattr(current_task().get_coro().cr_frame.f_locals.get("app"), name)

class FileIO:
    @classmethod
    async def save(app, file_path: str, mode: str = "wb", r=None):
        if not r: r = Context.r_sync()
        async with async_open(file_path, mode) as f:
            async for chunk in r.pull():
                if chunk: await f.write(chunk)

class Enterchunked:
    __slots__ = ("a", "k")

    def __init__(app, *a, **k):
        if not a or not isinstance(a[0], BlazeioProtocol):
            a = (Context.r_sync(), *a)

        if len(a) < 2:
            a = (*a, {})

        app.a, app.k = a, k

    async def __aenter__(app):
        app.a[1]["transfer-encoding"] = "chunked"
        await app.a[0].prepare(*app.a[1:], **app.k)
        return app

    async def __aexit__(app, exc_type=None, exc_value=None, traceback=None):
        await app.a[0].eof()

if __name__ == "__main__":
    pass
