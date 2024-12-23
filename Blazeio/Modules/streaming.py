from ..Dependencies import p, dumps, loads, Err, Log, sleep







class Deliver:
    @classmethod
    async def json(app, r, data: dict, status: int = 200, reason: str = "OK", headers: dict = {}, indent: int = 4):
        headers = dict(headers)

        headers["Content-Type"] = "application/json"
        
        await r.prepare(headers, status=status, reason=reason)

        await r.write(bytearray(dumps(data, indent=indent), "utf-8"))


    @classmethod
    async def text(app, r, data, status=200, reason="OK", headers={}):
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
