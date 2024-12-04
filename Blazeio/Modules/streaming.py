from ..Dependencies import p, dumps, loads, Err, Log
from .safeguards import SafeGuards

class Stream:
    response_headers = {
        'Server': 'Blazeio',
        'Strict-Transport-Security': 'max-age=63072000; includeSubdomains', 
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'origin-when-cross-origin'
    }

    @classmethod
    async def prepared(app, r):
        if "prepared" in r.__dict__: return True

    @classmethod
    async def init(app, r, headers={}, status=206, reason="Partial Content"):
        headers.update(app.response_headers)

        if await SafeGuards.is_alive(r):
            r.response.write(f"HTTP/1.1 {status} {reason}\r\n".encode())
            await r.response.drain()

            for key, val in headers.items():
                if await SafeGuards.is_alive(r):
                    r.response.write(f"{key}: {val}\r\n".encode())
                    await r.response.drain()

            if await SafeGuards.is_alive(r):
                r.response.write(b"\r\n")
                await r.response.drain()

            r.prepared = True
    
    @classmethod
    async def write(app, r, data: bytes):
        if await SafeGuards.is_alive(r):
            r.response.write(data)
            await r.response.drain()

class Deliver:
    @classmethod
    async def json(app, r, data, _dump=True, _encode=True, status=206, headers={}, reason="Partial Content"):
        if not "prepared" in r.__dict__:
            headers["Content-Type"] = "application/json"
            await Stream.init(r, headers, status=status, reason=reason)
        
        if isinstance(data, (dict,)):
            data = dumps(data)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await Stream.write(r, data)

    @classmethod
    async def text(app, r, data, status=206, headers={}, reason="Partial Content"):
        if not "prepared" in r.__dict__:
            headers["Content-Type"] = "text/plain"
            await Stream.init(r, headers, status=status, reason=reason)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await Stream.write(r, data)

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
        super().__init__(message)
        app.message = str(message)
        app.kwargs = kwargs
        app.status = status
        app.headers = headers

    def __str__(app) -> str:
        return app.message

    async def text(app, r):
        await Log.warning(r, app.message)

        await Deliver.text(
            r,
            app.message,
            app.status,
            app.headers,
            reason=app.kwargs.get("reason", "Forbidden")
        )

if __name__ == "__main__":
    pass
