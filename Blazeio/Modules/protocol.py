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

class BlazeioServerProtocol(BlazeioProtocol, BufferedProtocol, BlazeioPayloadUtils, ExtraToolset):
    __slots__ = ('on_client_connected','__stream__','__is_buffer_over_high_watermark__','__is_at_eof__','__is_alive__','transport','method','tail','path','headers','__is_prepared__','__status__','content_length','current_length','__perf_counter__','ip_host','ip_port','identifier','__cookie__','__miscellaneous__','__timeout__','__buff__','__buff__memory__','store','transfer_encoding','pull','write','encoder','encoder_obj','__evt__','__overflow_evt__','cancel')
    
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
        app.__buff__memory__ = memoryview(app.__buff__)
        app.__evt__ = SharpEvent(False)
        app.__overflow_evt__ = SharpEvent(False)
        app.cancel = None

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.cancel = lambda cancel = (task := loop.create_task(app.transporter())).cancel: cancel()

    def buffer_updated(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(app.__buff__memory__[:nbytes])
        app.__evt__.set()

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
            app.__buff__memory__ = memoryview(app.__buff__)
        elif sizehint <= 0:
            sizehint = len(app.__buff__memory__)

        return app.__buff__memory__[:sizehint]

    def connection_lost(app, exc):
        if app.cancel: app.cancel()
        app.__evt__.set()
        app.__overflow_evt__.set()

    def eof_received(app):
        app.__is_at_eof__ = True
        app.__evt__.set()

    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False
        app.__overflow_evt__.set()

    def prepend(app, data):
        if app.transport.is_reading(): app.transport.pause_reading()
        app.__stream__.appendleft(memoryview(data))
        app.__evt__.set()

    async def ensure_reading(app):
        if not app.transport.is_closing():
            if not app.__stream__ and not app.transport.is_reading():
                app.transport.resume_reading()

            await app.__evt__.wait()
            app.__evt__.clear()

    async def request(app):
        while True:
            await app.ensure_reading()
            while app.__stream__:
                yield bytes(app.__stream__.popleft())
            else:
                if app.transport.is_closing() or app.__is_at_eof__: break

    async def ayield(app, timeout: float = 10.0):
        async for chunk in app.request():
            yield chunk

    async def buffer_overflow_manager(app):
        if not app.__is_buffer_over_high_watermark__: return

        await app.__overflow_evt__.wait()
        app.__overflow_evt__.clear()

    async def writer(app, data: (bytes, bytearray)):
        await app.buffer_overflow_manager()

        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise ClientDisconnected()

if __name__ == "__main__":
    pass