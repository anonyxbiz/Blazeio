# Blazeio.Bench.Modules.Server.manager.py
import Blazeio as io

class RawServer:
    __slots__ = ("payload_size", "writes", "payload")
    def __init__(app, payload_size: int, writes: int):
        io.set_from_args(app, locals(), (int,))
        app.payload = b"." * app.payload_size

    async def _(app, r: io.BlazeioProtocol):
        await r.writer(
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/plain\r\n'
            b'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload\r\n'
            b'X-Frame-Options: DENY\r\n'
            b'X-Content-Type-Options: nosniff\r\n'
            b'X-XSS-Protection: 1; mode=block\r\n'
            b'Referrer-Policy: no-referrer-when-downgrade\r\n'
            b'Permissions-Policy: geolocation=(self), microphone=(), camera=()\r\n'
            b'Feature-Policy: accelerometer "none"; camera "none"; geolocation "self"; microphone "none"; usb "none"\r\n'
            b'Content-Security-Policy: default-src "self"; script-src "self"; object-src "none"; style-src "self";\r\n'
            b'Cache-Control: no-store, no-cache, must-revalidate, proxy-revalidate\r\n'
            b'Pragma: no-cache\r\n'
            b'Expires: 0\r\n'
            b'Server: Blazeio\r\n'
            b'Content-length: %d\r\n\r\n' % len(app.payload)*app.writes
        )

        await r.writer(app.payload*app.writes)

class PayloadServer:
    __slots__ = ("payload_size", "writes", "payload")
    def __init__(app, payload_size: int, writes: int):
        io.set_from_args(app, locals(), (int,))
        app.payload = b"." * app.payload_size

    async def _(app, r: io.BlazeioProtocol):
        await r.prepare({"Content-Type": r.headers.get("Content-type"), "Content-Length": str((len(app.payload)*app.writes))}, 200)

        for i in range(app.writes):
            await r.writer(app.payload)

class FileServer:
    __slots__ = ("root", "root_dir")
    def __init__(app, root: str, root_dir: str):
        io.set_from_args(app, locals(), (str,))
        app.configure()

    def configure(app):
        if not app.root:
            app.root = "/"
        app.root_dir = io.path.abspath(io.path.join(io.Scope.App.cwd, app.root_dir))

    async def handle_all_middleware(app, r: io.BlazeioProtocol):
        if not r.path.startswith(app.root):
            raise io.Abort("Not found", 404)

        if not io.path.exists(file := io.path.abspath(io.path.join(app.root_dir, r.path[1:]))):
            raise io.Abort("File not found", 404)

        if not io.path.abspath(file).startswith(app.root_dir):
            raise io.Abort("Access denied, file is outside the root directory", 403)

        await r.prepare({"Content-type": "text/html", "Transfer-encoding": "chunked"}, 200)
        
        start: int = 0
        async with io.async_open(file, "rb") as fd:
            while (chunk := await fd.read(io.ioConf.OUTBOUND_CHUNK_SIZE)):
                await r.write(chunk)
                start += len(chunk)
                fd.seek(start)

if __name__ == "__main__":
    ...