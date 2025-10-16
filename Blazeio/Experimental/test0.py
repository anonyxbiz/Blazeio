# Blazeio.Experimental.test0.py
import Blazeio as io

io.INBOUND_CHUNK_SIZE = 4096

web = io.App("0.0.0.0", 4096)

class Server:
    def __init__(app):
        ...

    async def __main_handler__(app, r: io.BlazeioProtocol):
        while not b'\r\n\r\n' in r.__buff__:
            await r.ensure_reading()

        if r.__stream__:
            r.__stream__.clear() # empty the __stream__ so that we can resume reading
        else:
            chunk = await r # Wait for a chunk to be received

        await r.writer(b"HTTP/1.1 200 OK\r\nContent-type: text/plain\r\nContent-length: 20\r\nContent-type: text/plain\r\nDate: Wed, 15 Oct 2025 19:43:47 GMT\r\nServer: Blazeio/2.7.3.7 (posix)\r\nConnection: keep-alive\r\n\r\n{'discovered': true}")

class Main(Server):
    def __init__(app):
        io.Super(app).__init__()

if __name__  == "__main__":
    web.attach(main := Main())
    with web:
        web.with_keepalive()
        web.runner()