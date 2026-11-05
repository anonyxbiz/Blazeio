# ./Other/Apps/Middleware/response_headers.py
import Blazeio as io

class ResponseHeaders:
    __slots__ = ("headers",)
    def __init__(app, **headers):
        app.headers = bytearray("".join(["%s: %s\r\n" % (key, value) for key, value in headers.items()]).encode())

    async def before_middleware(app, r: io.BlazeioProtocol):
        r += app.headers

if __name__ == "__main__":
    ...