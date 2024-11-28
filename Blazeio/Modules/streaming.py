from ..Dependencies import p, dumps, loads, Err, Log
from .safeguards import SafeGuards

class Stream:
    response_headers = {
        'Server': 'Unidentified-Anomalous-Phenomenon',
        'Strict-Transport-Security': 'max-age=63072000; includeSubdomains', 
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'origin-when-cross-origin'
    }

    @classmethod
    async def init(app, r, headers={}, **kwargs):
        headers.update(app.response_headers)
        status = kwargs.get("status", 206)
        reason = kwargs.get("reason", "Partial Content")

        if await SafeGuards.is_alive(r):
            r.response.write(f"HTTP/1.1 {status} {reason}\r\n".encode())
        
            for key, val in headers.items():
                if await SafeGuards.is_alive(r):
                    r.response.write(f"{key}: {val}\r\n".encode())
                    
            if await SafeGuards.is_alive(r):
                r.response.write(b"\r\n")
                if await SafeGuards.is_alive(r):
                    await r.response.drain()


            r.inited = True
    
    @classmethod
    async def write(app, r, data: bytes):
        if await SafeGuards.is_alive(r):
            r.response.write(data)
            if await SafeGuards.is_alive(r):
                await r.response.drain()

class Deliver:
    @classmethod
    async def json(app, r, data, _dump=True, _encode=True, status=206, headers={}, reason="Partial Content"):
        if not "inited" in r.__dict__:
            headers["Content-Type"] = "application/json"
            await Stream.init(r, headers, status=status, reason=reason)

        if _dump:
            data = dumps(data)
        
        if _encode:
            data = data.encode()

        await Stream.write(r, data)

    @classmethod
    async def text(app, r, data, status=206, headers={}, reason="Partial Content"):
        if not "inited" in r.__dict__:
            headers["Content-Type"] = "text/plain"
            await Stream.init(r, headers, status=status, reason=reason)

        await Stream.write(r, data.encode())

    @classmethod
    async def redirect(app, r, path, status=302, headers={}):
        headers["Location"] = path
        await Stream.init(r, headers, status=status)

class Abort(Exception):
    def __init__(app, message="Something went wrong", status=403, **kwargs):
        super().__init__(message)
        app.message = str(message)
        app.kwargs = kwargs
        app.status = status

    def __str__(app) -> str:
        return app.message

    async def text(app, r):
        await Deliver.text(r, app.message, app.status, reason=app.kwargs.get("reason", "Forbidden"))

if __name__ == "__main__":
    pass
