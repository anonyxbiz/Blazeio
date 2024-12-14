from ..Dependencies import p, dumps, loads, Err, Log, sleep

class Stream:
    @classmethod
    async def init(app, r, *args, **kwargs):
        await r.prepare(*args, **kwargs)
        
        r.prepared = True

    @classmethod
    async def write(app, r, data: bytes):
        await r.write(data)

    @classmethod
    async def prepared(app, r):
        if "prepared" in r.__dict__: return True
            
class Deliver:
    @classmethod
    async def json(app, r, data, _dump=True, _encode=True, status=206, headers={}, reason="Partial Content", indent=4):
        headers["Content-Type"] = "application/json"
        await Stream.init(r, headers, status=status, reason=reason)

        if isinstance(data, (dict,)):
            data = dumps(data, indent=indent)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await r.write(data)

    @classmethod
    async def prepare_text(app, r, headers={}, **kwargs):
        headers["Content-Type"] = "text/plain"
        await Stream.init(r, headers, **kwargs)

    @classmethod
    async def text(app, r, data, status=206, headers={}, reason="Partial Content"):
        headers["Content-Type"] = "text/plain"
        await Stream.init(r, headers, status=status, reason=reason)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await r.write(data)

    @classmethod
    async def redirect(app, r, path, status=302, headers={}):
        headers["Location"] = path
        await Stream.init(r, headers, status=status)

    @classmethod
    async def HTTP_301(app, r, path, status=301, headers={}):
        headers["Location"] = path
        await Stream.init(r, headers, status=status)

    @classmethod
    async def HTTP_302(app, r, path, status=302, headers={}):
        headers["Location"] = path
        await Stream.init(r, headers, status=status)

    @classmethod
    async def HTTP_307(app, r, path, status=307, headers={}):
        headers["Location"] = path
        await Stream.init(r, headers, status=status)

    @classmethod
    async def HTTP_308(app, r, path, status=308, headers={}):
        headers["Location"] = path
        await Stream.init(r, headers, status=status)

class Abort(Exception):
    def __init__(app, message="Something went wrong", status=403, headers={}, **kwargs):
        app.message = str(message)
        app.kwargs = kwargs
        app.status = status
        app.headers = headers
        super().__init__(message)

    def __str__(app) -> str:
        return app.message

    async def text(app, r):
        await Deliver.text(
            r,
            app.message,
            app.status,
            app.headers,
            reason=app.kwargs.get("reason", "Forbidden")
        )

if __name__ == "__main__":
    pass
