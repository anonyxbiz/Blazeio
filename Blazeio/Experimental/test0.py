# Blazeio.Experimental.test0.py
import Blazeio as io

io.INBOUND_CHUNK_SIZE = 4096

web = io.App("0.0.0.0", 4096)

class Server:
    http_line = b"\r\n\r\n"
    def __init__(app):
        ...
    
    async def handler(app, r: io.BlazeioProtocol):
        # Now the actual handler can handle the request, if its an upload, stream it to disk, or stream it to an upstream server
        await r.writer(b"HTTP/1.1 200 OK\r\nContent-type: text/plain\r\nContent-length: 20\r\nContent-type: text/plain\r\nDate: Wed, 15 Oct 2025 19:43:47 GMT\r\nServer: Blazeio/2.7.3.7 (posix)\r\nConnection: keep-alive\r\n\r\n{'discovered': true}")

    def parser(app, r: io.BlazeioProtocol, buff: bytes):
        idx = buff.find(app.http_line)
        header, buff = buff[:idx], buff[idx + len(app.http_line):]
        # Call a c-extension here to parse the request

        # prepend the remainder to the request stream for the next iter to yield

        r.prepend(buff)

    async def __main_handler__(app, r: io.BlazeioProtocol):
        buff = bytearray()

        # Buffer chunks until end of headers
        while not app.http_line in buff:
            buff.extend(await r)

        app.parser(r, buff)

        await app.handler(r)

class Main(Server):
    def __init__(app):
        io.Super(app).__init__()

if __name__  == "__main__":
    web.attach(main := Main())
    with web:
        web.with_keepalive()
        web.runner()