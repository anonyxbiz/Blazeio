from ..Dependencies import *

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
        r = await Context.r()
        headers = dict(headers)
        headers["Content-Type"] = content_type

        await r.prepare(headers, status)

    @classmethod
    async def json(app, headers: dict={}, status:int = 206, content_type: str = "application/json; charset=utf-8"):
        r = await Context.r()
        headers = dict(headers)
        headers["Content-Type"] = content_type

        await r.prepare(headers, status)

class Deliver:
    @classmethod
    async def json(app, r, data: dict = {}, status: int = 200, headers: dict = {}, indent: int = 4, content_type: str = "application/json; charset=utf-8"):
        headers = dict(headers)
        headers["Content-Type"] = content_type
        await r.prepare(headers, status)
        await r.write(bytearray(dumps(data, indent=indent), "utf-8"))

    @classmethod
    async def text(app, r, data, status=200, headers={}, content_type: str = "text/plain; charset=utf-8"):
        headers = dict(headers)
        headers["Content-Type"] = content_type
        await r.prepare(headers, status)
        await r.write(bytearray(data, "utf-8"))

    @classmethod
    async def redirect(app, r, path, status=302, headers={}, reason=None):
        headers["Location"] = path
        await r.prepare(headers, status=status)

    @classmethod
    async def HTTP_301(app, r, path, status=301, headers={}, reason=None):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_302(app, r, path, status=302, headers={}, reason=None):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_307(app, r, path, status=307, headers={}, reason=None):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_308(app, r, path, status=308, headers={}, reason=None):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

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

    async def text(app):
        message = app.args[0] if len(app.args) >= 1 else "Something went wrong"
        status = app.args[1] if len(app.args) >= 2 else 403
        headers = app.args[2] if len(app.args) >= 3 else {}

        headers["Content-Type"] = "text/plain; charset=utf-8"
        
        try:
            await app.r.prepare(headers, status)
            await app.r.write(message.encode())
        except Err:
            return

class Eof(Exception):
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

    async def text(app):
        message = app.args[0] if len(app.args) >= 1 else "Something went wrong"
        await app.r.write(message.encode())

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
            async for chunk in r.pull(): await f.write(chunk)

if __name__ == "__main__":
    pass
