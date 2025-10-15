import Blazeio as io

io.INBOUND_CHUNK_SIZE = 4096

web = io.App("0.0.0.0", 90)

@web.add_route
async def __main_handler__(r):
    while not b'\r\n\r\n' in r.__buff__:
        await r.ensure_reading()

    if r.__stream__:
        # await io.plog.yellow(r.__stream__)
        r.__stream__.clear()
    else:
        r.transport.resume_reading() # Allow the transport to receive more data

    await r.writer(b"HTTP/1.1 200 OK\r\nContent-type: text/plain\r\nContent-length: 20\r\nContent-type: text/plain\r\nDate: Wed, 15 Oct 2025 19:43:47 GMT\r\nServer: Blazeio/2.7.3.7 (posix)\r\nConnection: keep-alive\r\n\r\n{'discovered': true}")

with web:
    web.with_keepalive()
    web.runner()