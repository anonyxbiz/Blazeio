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
        headers_ = dict(headers)
        
        headers_["Content-Type"] = "application/json"
        await r.prepare(headers_, status=status, reason=reason)

        if isinstance(data, (dict,)):
            data = dumps(data, indent=indent)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await r.write(data)

    @classmethod
    async def text(app, r, data, status=206, reason="Partial Content", headers={}):
        headers = dict(headers)

        headers["Content-Type"] = "text/plain"
        
        await r.prepare(headers, status=status, reason=reason)

        await r.write(bytearray(data, "utf-8"))

    @classmethod
    async def redirect(app, r, path, status=302, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status)

    @classmethod
    async def HTTP_301(app, r, path, status=301, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_302(app, r, path, status=302, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_307(app, r, path, status=307, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_308(app, r, path, status=308, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

class Abort(Exception):
    def __init__(
        app,
        *args,
        **kwargs
    ):
        app.args, app.kwargs = args, kwargs

    def __str__(app) -> str:
        return str(app.message)
    
    async def text(app, r, message: str = "Something went wrong", status: int = 403, reason: str = "Forbidden", headers: dict = {}
    ):
        try:
            headers_ = {
                "Content-Type": "text/plain"
            }
            
            if headers: headers_.update(headers)
            
            await r.prepare(
                headers_,
                status,
                reason
            )
            
            await r.write(bytearray(message, "utf-8"))
            
        except Exception as e:
            await Log.critical(r, e)
        
if __name__ == "__main__":
    pass
