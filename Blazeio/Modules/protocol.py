from ..Dependencies import *
from .extratools import *

class BlazeioPayloadUtils:
    __slots__ = ()
    non_bodied_methods = {"GET", "HEAD", "OPTIONS"}

    def __init__(app):
        pass

    async def transporter(app):
        await app.on_client_connected(app)
        await app.close()

    async def control(app, duration=0):
        await sleep(duration)

    async def close(app):
        await sleep(0)
        app.transport.close()

class BlazeioServerProtocol(BufferedProtocol, BlazeioPayloadUtils, ExtraToolset):
    __slots__ = (
        'on_client_connected',
        '__stream__',
        '__is_buffer_over_high_watermark__',
        '__is_at_eof__',
        '__is_alive__',
        'transport',
        'method',
        'tail',
        'path',
        'headers',
        '__is_prepared__',
        '__status__',
        'content_length',
        'current_length',
        '__perf_counter__',
        'ip_host',
        'ip_port',
        'identifier',
        '__cookie__',
        '__miscellaneous__',
        '__timeout__',
        '__buff__',
        '__stream__sleep',
        '__overflow_sleep',
        '__buff__memory__',
        'store',
        'transfer_encoding',
        'pull',
        'write',
        'encoder',
        'encoder_obj',
    )
    
    def __init__(app, on_client_connected, INBOUND_CHUNK_SIZE=None):
        app.on_client_connected = on_client_connected
        app.__buff__ = bytearray(INBOUND_CHUNK_SIZE)
        app.__stream__ = deque()
        app.__is_buffer_over_high_watermark__ = False
        app.__is_at_eof__ = False
        app.__is_alive__ = True
        app.method = None
        app.tail = "handle_all_middleware"
        app.path = "handle_all_middleware"
        app.headers = None
        app.__is_prepared__ = False
        app.__status__ = 0
        app.content_length = None
        app.transfer_encoding = None
        app.current_length = 0
        app.__cookie__ = None
        app.__miscellaneous__ = None
        app.store = None
        app.__timeout__ = None
        app.__stream__sleep = 0
        app.__overflow_sleep = 0
        app.__buff__memory__ = memoryview(app.__buff__)

        for i in app.__class__.__bases__: i.__init__(app)

    async def buffer_overflow_manager(app):
        if not app.__is_buffer_over_high_watermark__: return

        while app.__is_buffer_over_high_watermark__:
            await sleep(app.__overflow_sleep)

    async def prepend(app, data):
        if app.transport.is_reading(): app.transport.pause_reading()

        sizehint = len(data)

        app.__buff__ = bytearray(data) + app.__buff__ 

        app.__buff__memory__ = memoryview(app.__buff__)

        app.__stream__.appendleft(sizehint)

    async def ensure_reading(app):
        if not app.transport.is_reading() and not app.__stream__:
            app.transport.resume_reading()

    async def request(app):
        while True:
            await app.ensure_reading()

            while app.__stream__:
                chunk = bytes(app.__buff__memory__[:app.__stream__.popleft()])

                yield chunk
                await app.ensure_reading()

            if not app.__stream__:
                if app.transport.is_closing() or app.__is_at_eof__: break

            await sleep(app.__stream__sleep)

            if not app.__stream__: yield None

    async def ayield(app, timeout = None):
        if not timeout: timeout = app.__timeout__ or 60.0
        idle_time = None

        async for chunk in app.request():
            yield chunk

            if chunk is not None:
                if idle_time is not None:
                    idle_time = None
            else:
                if idle_time is None:
                    idle_time = perf_counter()
                
                if perf_counter() - idle_time > timeout:
                    break

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        loop.create_task(app.transporter())

    def buffer_updated(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(nbytes)

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
            app.__buff__memory__ = memoryview(app.__buff__)

        return app.__buff__memory__[:sizehint]

    def connection_lost(app, exc):
        app.__is_alive__ = False

    def eof_received(app):
        app.__is_at_eof__ = True

    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False

if __name__ == "__main__":
    pass