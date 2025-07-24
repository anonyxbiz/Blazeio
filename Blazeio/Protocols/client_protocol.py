# Blazeio.Protocols.client_protocol
from ..Dependencies import *
from ..Modules.request import *
from .client_protocol_tools import *

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
        '__timeout__',
        'cancel_on_disconnect',
        '__wait_closed__',
    )

    def __init__(app, **kwargs):
        app.__chunk_size__ = kwargs.get("__chunk_size__", ioConf.OUTBOUND_CHUNK_SIZE)
        app.__timeout__ = kwargs.get("__timeout__", kwargs.get("timeout"))
        app.__is_at_eof__ = False
        app.cancel_on_disconnect = False
        app.__perf_counter__ = perf_counter()
        app.__stream__ = deque()
        app.__buff__ = bytearray(app.__chunk_size__)
        app.__buff__memory__ = memoryview(app.__buff__)
        app.__is_buffer_over_high_watermark__ = False
        app.__evt__ = SharpEvent(evloop = kwargs.get("evloop"))
        app.__overflow_evt__ = SharpEvent(evloop = kwargs.get("evloop"))
        app.__wait_closed__ = SharpEvent(evloop = kwargs.get("evloop"))
        if (task := current_task()): task.__BlazeioClientProtocol__ = app

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport

    def state(app):
        return {key: str(value)[:500] if not isinstance(value := getattr(app, key, ""), (int, str)) else value for key in app.__class__.__slots__}

    def cancel(app):
        app.__wait_closed__.set()
        app.transport.close()

    async def pull(app):
        while True:
            await app.ensure_reading()
            while app.__stream__:
                yield app.__stream__.popleft()
            else:
                if app.transport.is_closing() or app.__is_at_eof__: break

    async def push(app, data: (bytes, bytearray)):
        await app.buffer_overflow_manager()

        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise ServerDisconnected()

if __name__ == "__main__":
    pass