# Blazeio.Bench.Modules.Server.manager.py
import Blazeio as io

class BareMetalServer:
    __slots__ = ("payload_size", "writes", "payload")
    def __init__(app, payload_size: int, writes: int):
        io.set_from_args(app, locals(), (int,))
        app.payload = b"." * app.payload_size
    
    def minimal_parser(app, r: io.BlazeioProtocol):
        # Just extract the request
        if (protocol_start := r.__buff__.find(io.MinParsers.server.network_config.http.one_point_one.protocol)) == -1 or (protocol_end := r.__buff__.find(io.MinParsers.server.network_config.http.one_point_one.dcrlf)) == -1:
            raise io.Abort("Bad request", 403)

        return r.__buff__[protocol_start:protocol_end] # This is the http request

    async def __main_handler__(app, r: io.BlazeioProtocol):
        while 1:
            while not io.MinParsers.server.network_config.http.one_point_one.dcrlf in r.__buff__: # Check if the http dcrlf is in the stream buffer
                await r # await some data

            app.minimal_parser(r)

            await r.writer(
                b'HTTP/1.1 200 OK\r\n'
                b'Content-Type: text/plain\r\n'
                b'Connection: keepalive\r\n'
                b'Server: Blazeio\r\n'
                b'Content-length: %d\r\n\r\n' % len(app.payload)*app.writes
            )

            for i in range(app.writes):
                await r.writer(app.payload)

class RawServer:
    __slots__ = ("payload_size", "writes", "payload")
    def __init__(app, payload_size: int, writes: int):
        io.set_from_args(app, locals(), (int,))
        app.payload = b"." * app.payload_size

    async def _(app, r: io.BlazeioProtocol):
        await r.writer(
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/plain\r\n'
            b'Connection: keepalive\r\n'
            b'Server: Blazeio\r\n'
            b'Content-length: %d\r\n\r\n' % len(app.payload)*app.writes
        )

        for i in app.writes:
            await r.writer(app.payload)

class PayloadServer:
    __slots__ = ("payload_size", "writes", "payload")
    def __init__(app, payload_size: int, writes: int):
        io.set_from_args(app, locals(), (int,))
        app.payload = b"." * app.payload_size

    async def _(app, r: io.BlazeioProtocol):
        await r.prepare({"Content-Type": r.headers.get("Content-type"), "Content-Length": str((len(app.payload)*app.writes))}, 200)
        
        for i in app.writes:
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