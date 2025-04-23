from ..Dependencies import *
from ..Modules.request import *

class BlazeioClientProtocol(BufferedProtocol):
    __slots__ = (
        '__is_at_eof__',
        'transport',
        '__buff__',
        '__stream__',
        '__buff_requested__',
        '__buff__memory__',
        '__chunk_size__',
        '__evt__',
        '__is_buffer_over_high_watermark__',
        '__overflow_evt__',
        '__continous__',
        '__perf_counter__',
        '__timeout__'
    )

    def __init__(app, **kwargs):
        app.__chunk_size__ = kwargs.get("__chunk_size__", OUTBOUND_CHUNK_SIZE)

        app.__is_at_eof__ = False
        app.__buff_requested__ = False
        app.__continous__ = 0
        app.__perf_counter__ = perf_counter()
        app.__timeout__ = 60.0

        if kwargs:
            for key in kwargs:
                if key in app.__slots__:
                    setattr(app, key, kwargs[key])

        app.__stream__ = deque()
        app.__buff__ = bytearray(app.__chunk_size__)
        app.__buff__memory__ = memoryview(app.__buff__)
        app.__is_buffer_over_high_watermark__ = False
        app.__evt__ = Event()
        app.__overflow_evt__ = Event()

    def connection_made(app, transport):
        if not app.__continous__: transport.pause_reading()
        app.transport = transport
        ReMonitor.client_queue.put_nowait(app)

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

    async def set_buffer(app, sizehint: int = 0):
        if app.transport.is_reading(): app.transport.pause_reading()

        app.__is_at_eof__ = False
        app.__buff_requested__ = False
        app.__stream__.clear()
        app.__buff__ = bytearray(sizehint or app.__chunk_size__)
        app.__buff__memory__ = memoryview(app.__buff__)
        app.__is_buffer_over_high_watermark__ = False
        app.__evt__ = Event()
        app.__overflow_evt__ = Event()

    async def prepend(app, data):
        app.transport.pause_reading()

        if not app.__continous__:
            sizehint = len(data)
            app.__buff__ = bytearray(data) + app.__buff__
            app.__buff__memory__ = memoryview(app.__buff__)
            app.__stream__.appendleft(sizehint)
        else:
            app.__stream__.appendleft(data)

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

    async def pull(app):
        if not app.__continous__:
            puller = app.pull_paused()
        else:
            puller = app.pull_continous()

        async for i in puller: yield i

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