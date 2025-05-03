from ..Dependencies import *
from ..Modules.request import *

class BlazeioClientProtocol(BufferedProtocol):
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
        '__continous__',
        'pull',
        'max_continous_len',
        '__perf_counter__',
        '__timeout__'
    )

    def __init__(app, **kwargs):
        app.__chunk_size__: int = kwargs.get("__chunk_size__", ioConf.OUTBOUND_CHUNK_SIZE)

        app.__is_at_eof__: bool = False
        app.__continous__: (int, bool) = 0
        app.__perf_counter__: int = perf_counter()
        app.__timeout__: float = 60.0
        app.max_continous_len: int = 200

        if kwargs:
            for key in kwargs:
                if key in app.__slots__:
                    setattr(app, key, kwargs[key])

        app.__stream__: deque = deque()
        app.__buff__: bytearray = bytearray(app.__chunk_size__)
        app.__buff__memory__: memoryview = memoryview(app.__buff__)
        app.__is_buffer_over_high_watermark__: bool = False
        app.__evt__: SharpEventManual = SharpEventManual()
        app.__overflow_evt__: SharpEventManual = SharpEventManual()
        app.pull = app.pull_continous if app.__continous__ else app.pull_paused

    def connection_made(app, transport):
        if not app.__continous__: transport.pause_reading()
        app.transport = transport

    def eof_received(app):
        app.__is_at_eof__ = True
        app.__evt__.set()

    def connection_lost(app, exc):
        app.__evt__.set()
        app.__overflow_evt__.set()

    def buffer_updated_paused(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(nbytes)
        app.__evt__.set()

    def buffer_updated_continous(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(app.__buff__memory__[:nbytes])
        app.__evt__.set()

    def buffer_updated(app, *args):
        if not app.__continous__:
            app.buffer_updated_paused(*args)
        else:
            app.buffer_updated_continous(*args)

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
            app.__buff__memory__ = memoryview(app.__buff__)
        elif sizehint <= 0:
            sizehint = len(app.__buff__memory__)

        return app.__buff__memory__[:sizehint]

    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False
        app.__overflow_evt__.set()

    async def buffer_overflow_manager(app):
        if not app.__is_buffer_over_high_watermark__: return

        await app.__overflow_evt__.wait()
        app.__overflow_evt__.clear()

    async def prepend(app, data):
        app.transport.pause_reading()

        if not app.__continous__:
            sizehint = len(data)
            app.__buff__ = bytearray(data) + app.__buff__
            app.__buff__memory__ = memoryview(app.__buff__)
            app.__stream__.appendleft(sizehint)
        else:
            app.__stream__.appendleft(memoryview(data))

        app.__evt__.set()

    async def ensure_reading(app):
        if not app.transport.is_closing():
            if not app.__stream__ and not app.transport.is_reading():
                app.transport.resume_reading()

            await app.__evt__.wait()
            app.__evt__.clear()

    async def pull_paused(app):
        while True:
            await app.ensure_reading()
            while app.__stream__:
                yield bytes(app.__buff__memory__[:app.__stream__.popleft()])
                app.transport.resume_reading()
            else:
                if app.transport.is_closing(): break

    async def pull_continous(app):
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
            raise Err("Client has disconnected.")

    async def ayield(app, timeout: float = 10.0):
        async for chunk in app.pull():
            yield chunk

if __name__ == "__main__":
    pass