# Blazeio.Experimental.test0.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser

io.INBOUND_CHUNK_SIZE = 4096

web = io.App("0.0.0.0", 4096)

class Server:
    def __init__(app):
        ...

    def connection_closure(app, r: io.BlazeioProtocol, canceller):
        return canceller()

    async def __main_handler__(app, r: io.BlazeioProtocol):
        if r.cancel.__name__ == "cancel":
            r.cancel = lambda cancel = r.cancel, r = r: app.connection_closure(r, cancel)

        while not b'\r\n\r\n' in r.__buff__:
            await r.ensure_reading()

        if r.__stream__:
            r.__stream__.clear() # empty the __stream__ so that we can resume reading
        else:
            r.transport.resume_reading() # Allow the transport to receive more data
    
        await r.writer(b"HTTP/1.1 200 OK\r\nContent-type: text/plain\r\nContent-length: 20\r\nContent-type: text/plain\r\nDate: Wed, 15 Oct 2025 19:43:47 GMT\r\nServer: Blazeio/2.7.3.7 (posix)\r\nConnection: keep-alive\r\n\r\n{'discovered': true}")

class Main(Server):
    def __init__(app):
        io.set_from_args(app, locals(), io.Utype)
        io.Super(app).__init__()

if __name__  == "__main__":
    web.attach(main := Main(**class_parser.Parser(Main, io.Utype).args()))

    with web:
        web.with_keepalive()
        web.runner()