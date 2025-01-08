from ..Dependencies import p, dumps, loads, Err, Log, sleep







class Deliver:
    @classmethod
    async def json(app, r, data: dict, status: int = 200, headers: dict = {}, indent: int = 4):
        headers = dict(headers)
        headers["Content-Type"] = "application/json; charset=utf-8"
        await r.prepare(headers, status)
        await r.write(bytearray(dumps(data, indent=indent), "utf-8"))

    @classmethod
    async def text(app, r, data, status=200, headers={}):
        headers = dict(headers)

        headers["Content-Type"] = "text/plain; charset=utf-8"
        
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

class Abort(Exception):
    __slots__ = (
        'args',
    )

    def __init__(
        app,
        *args
    ):
        app.args = args

    async def text(
        app,
        r,
        message: str = "Something went wrong",
        status: int = 403,
        headers: dict = {},
    ):
        try:
            headers = dict(headers)

            headers.update({
                "Content-Type": "text/plain"
            })

            await r.prepare(
                headers,
                status
            )

            await r.write(message.encode())

        except Exception as e:
            await Log.critical(r, e)
        
if __name__ == "__main__":
    pass
