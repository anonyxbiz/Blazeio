# Blazeio.Experimental.test0.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser

io.INBOUND_CHUNK_SIZE = 4096

web = io.App("0.0.0.0", 4096)

web.with_keepalive()

class Tester:
    def __init__(app):
        if app.local:
            [io.getLoop.create_task(app.test_srv()) for i in range(app.conns)]

    async def __aenter__(app):
        await web # Wait for the server to start
        return app
    
    async def __aexit__(app, *args):
        await web.exit()
        return False

    async def test_srv(app):
        # io.getSession is a task-scoped connection pool
        async with app:
            for i in range(app.requests):
                async with io.getSession.get("http://localhost:%d/" % web.ServerConfig.port) as resp:
                    await io.plog.grey(io.anydumps(io.ddict(state = resp.state, status_code = resp.status_code, headers = resp.headers, body = await resp.text())))

class Server:
    canceller_name = "cancel"
    def __init__(app):
        ...

    def connection_closure(app, r: io.BlazeioProtocol, canceller):
        return canceller()

    async def __main_handler__(app, r: io.BlazeioProtocol):
        if r.cancel.__name__ == app.canceller_name:
            r.cancel = lambda canceller = r.cancel, r = r: app.connection_closure(r, canceller)

        while not b'\r\n\r\n' in r.__buff__:
            await r.ensure_reading()

        if r.__stream__:
            r.__stream__.clear() # empty the __stream__ so that we can resume reading
        else:
            r.transport.resume_reading() # Allow the transport to receive more data
    
        await r.writer(b"HTTP/1.1 200 OK\r\nContent-type: text/plain\r\nContent-length: 20\r\nContent-type: text/plain\r\nDate: Wed, 15 Oct 2025 19:43:47 GMT\r\nServer: Blazeio/2.7.3.7 (posix)\r\nConnection: keep-alive\r\n\r\n{'discovered': true}")

class Main(Tester, Server):
    def __init__(app, local: (bool, io.Utype, class_parser.Store) = io.debug_mode, conns: (int, io.Utype) = 1, requests: (int, io.Utype) = 10):
        io.set_from_args(app, locals(), io.Utype)
        io.Super(app).__init__()

if __name__  == "__main__":
    web.attach(main := Main(**class_parser.Parser(Main, io.Utype).args()))

    with web:
        web.runner()