from ..Dependencies import *
from ..Modules.request import *

class BlazeioClientProtocol(BlazeioProtocol, BufferedProtocol):
    __slots__ = (
        '__is_at_eof__',
        'transport',
        '__buff__',
        '__stream__',
        '__buff__memory__',
        '__chunk_size__',
        '__evt__',
        '__is_buffer_over_high_watermark__',
        '__overflow_evt__',
        '__perf_counter__',
        '__timeout__'
    )

    def __init__(app, **kwargs):
        app.__chunk_size__: int = kwargs.get("__chunk_size__", ioConf.OUTBOUND_CHUNK_SIZE)
        app.__timeout__: float = kwargs.get("__timeout__", 60.0)
        app.__is_at_eof__: bool = False
        app.__perf_counter__: int = perf_counter()
        app.__stream__: deque = deque()
        app.__buff__: bytearray = bytearray(app.__chunk_size__)
        app.__buff__memory__: memoryview = memoryview(app.__buff__)
        app.__is_buffer_over_high_watermark__: bool = False
        app.__evt__: SharpEvent = SharpEvent(False)
        app.__overflow_evt__: SharpEvent = SharpEvent(False)

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport

    def eof_received(app):
        app.__is_at_eof__ = True
        app.__evt__.set()

    def connection_lost(app, exc):
        app.__evt__.set()
        app.__overflow_evt__.set()

    def buffer_updated(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(app.__buff__memory__[:nbytes])
        app.__evt__.set()

    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False
        app.__overflow_evt__.set()

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
            app.__buff__memory__ = memoryview(app.__buff__)
        elif sizehint <= 0:
            sizehint = len(app.__buff__memory__)

        return app.__buff__memory__[:sizehint]

    async def buffer_overflow_manager(app):
        if not app.__is_buffer_over_high_watermark__: return

        await app.__overflow_evt__.wait()
        app.__overflow_evt__.clear()

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

    async def pull(app):
        while True:
            await app.ensure_reading()
            while app.__stream__:
                yield bytes(app.__stream__.popleft())
                app.transport.resume_reading()
            else:
                if app.transport.is_closing(): break

    async def push(app, data: (bytes, bytearray)):
        await app.buffer_overflow_manager()

        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise ServerDisconnected()

    async def ayield(app, timeout: float = 10.0):
        async for chunk in app.pull():
            yield chunk

if __name__ == "__main__":
    pass