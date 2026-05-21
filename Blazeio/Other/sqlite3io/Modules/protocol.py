# ./Other/sqlite3io/Modules/protocol.py
import Blazeio as io

class Parser:
    __slots__ = ("prot", "buff", "size", "row_count")
    delimiter: bytes = b"\x15"
    def __init__(app, prot):
        app.prot, app.buff, app.size, app.row_count = prot, bytearray(), None, 0

    def parse(app):
        if app.size is None:
            if (idx := app.buff.find(app.delimiter)) == -1: return

            buff = app.buff[idx + len(app.delimiter):]

            if (idx := buff.find(app.delimiter)) == -1: return

            app.size, app.buff = int(buff[:idx], 16), buff[idx + len(app.delimiter):]

        if len(app.buff) < app.size: return

        chunk, app.buff, app.size = bytes(app.buff[:app.size]), app.buff[app.size:], None
        app.row_count += 1

        return chunk

    async def __aiter__(app):
        try:
            async for chunk in app.prot:
                app.buff.extend(chunk)
                while (chunk := app.parse()): yield chunk
        except GeneratorExit:
            return

class ServerParser:
    __slots__ = ("prot", "delimiter")
    default_headers: dict = {"Transfer-encoding": "chunked", "Content-type": "video/mp4", "Cache-Control": "no-store, no-cache, must-revalidate, private", "Cloudflare-CDN-Cache-Control": "no-store, no-cache", "Pragma": "no-cache", "X-Accel-Buffering": "no"}
    default_delimiter: str = "\x15"
    def __init__(app, r: io.BlazeioProtocol):
        app.prot, app.delimiter = r, str(r.headers.get("X-sqlliteio-delimiter", app.default_delimiter)).encode()

    def mux(app, data):
        return b"%b%X%b%b" % (app.delimiter, len(data), app.delimiter, data.encode() if not isinstance(data, bytes) else data)

    def write(app, data):
        return app.prot.write(app.mux(data))

    async def __aenter__(app):
        await app.prot.prepare(app.default_headers, 200)
        return app

    async def __aexit__(app, *args):
        return False
        
class Sqlite3ioEvent:
    __slots__ = ("session", "stream", "headers", "status_code")
    def __init__(app, session):
        app.session = session

    def __call__(app, *args, **kwargs):
        return app.events(*args, **kwargs)

    async def events(app, q: str):
        async with io.getSession.post("%s/events/await" % app.session.url, {"X-sqlliteio-hmac-sha256-hash": app.session.signature_client.sign(str(app.session.signature_client.get_current_timestamp()).encode())}, json = {"q": q}) as resp:
            if not resp.ok():
                raise io.Abort(await resp.text(), resp.status_code)

            async for event in Parser(resp):
                yield io.ddict(io.loads(event.decode()))

if __name__ == "__main__": ...