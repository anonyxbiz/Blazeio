from ..Dependencies import *
from ..Modules.request import *

class BlazeioClientProtocol(BufferedProtocol):
    __slots__ = (
        '__is_at_eof__',
        '__is_alive__',
        'transport',
        '__buff__',
        '__stream__',
        '__buff_requested__',
        '__buff__memory__',
        '__stream__sleep',
        '__chunk_size__',
    )

    def __init__(app, **kwargs):
        app.__chunk_size__ = kwargs.get("__chunk_size__", OUTBOUND_CHUNK_SIZE)

        app.__is_at_eof__ = False
        app.__buff_requested__ = False
        app.__stream__sleep = 0
        
        if kwargs:
            for key, val in kwargs.items():
                if key in app.__slots__:
                    setattr(app, key, val)

        app.__stream__ = deque()
        app.__buff__ = bytearray(app.__chunk_size__)
        app.__buff__memory__ = memoryview(app.__buff__)

    async def set_buffer(app, sizehint: int):
        if app.transport.is_reading(): app.transport.pause_reading()

        app.__buff__ = app.__buff__ + bytearray(sizehint)

        app.__buff__memory__ = memoryview(app.__buff__)

    async def prepend(app, data):
        if app.transport.is_reading(): app.transport.pause_reading()
        sizehint = len(data)
        app.__buff__ = bytearray(data) + app.__buff__ 
        app.__buff__memory__ = memoryview(app.__buff__)
        app.__stream__.appendleft(sizehint)

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.__is_alive__ = True

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc):
        app.__is_alive__ = False

    def buffer_updated(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(nbytes)

    async def ensure_reading(app):
        if not app.transport.is_reading() and not app.__stream__:
            app.transport.resume_reading()

    async def pull(app):
        while True:
            await app.ensure_reading()

            while app.__stream__:
                yield bytes(app.__buff__memory__[:app.__stream__.popleft()])

                await app.ensure_reading()

            if not app.__stream__:
                if app.transport.is_closing() or app.__is_at_eof__: break

            await sleep(app.__stream__sleep)

            if not app.__stream__: yield None

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
        elif sizehint <= 0:
            sizehint = len(app.__buff__memory__)

        return app.__buff__memory__[:sizehint]

    async def push(app, data: (bytes, bytearray)):
        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

    async def ayield(app, timeout: float = 10.0):
        idle_time = None

        async for chunk in app.pull():
            yield chunk

            if chunk is not None:
                if idle_time is not None:
                    idle_time = None
            else:
                if idle_time is None:
                    idle_time = perf_counter()
                
                if perf_counter() - idle_time > timeout:
                    break

if __name__ == "__main__":
    pass