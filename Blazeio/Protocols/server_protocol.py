from ..Dependencies import *
from .server_protocol_extratools import *

class BlazeioPayloadUtils:
    __slots__ = ()
    non_bodied_methods = {"GET", "HEAD", "OPTIONS"}
    async def transporter(app):
        await app.on_client_connected(app)
        app.close()

    def control(app, duration=0):
        return sleep(duration)

    def close(app):
        app.transport.close()

class BlazeioServerProtocol(BlazeioProtocol, BufferedProtocol, BlazeioPayloadUtils, ExtraToolset):
    __slots__ = ('on_client_connected','__stream__','__is_buffer_over_high_watermark__','__is_at_eof__','__is_alive__','transport','method','tail','path','headers','__is_prepared__','__status__','content_length','current_length','__perf_counter__','ip_host','ip_port','identifier','__cookie__','__miscellaneous__','__timeout__','__buff__','__buff__memory__','store','transfer_encoding','pull','write','encoder','encoder_obj','__evt__','__overflow_evt__','cancel', 'cancel_on_disconnect',)
    
    def __init__(app, on_client_connected, evloop, INBOUND_CHUNK_SIZE=None):
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
        app.__evt__ = SharpEvent(False, evloop)
        app.__overflow_evt__ = SharpEvent(False, evloop)
        app.cancel_on_disconnect = True

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.cancel = (task := loop.create_task(app.transporter())).cancel

    async def request(app):
        while True:
            await app.ensure_reading()
            while app.__stream__:
                yield app.__stream__.popleft()
            else:
                if app.transport.is_closing() or app.__is_at_eof__: break

    async def writer(app, data: (bytes, bytearray)):
        await app.buffer_overflow_manager()

        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise ClientDisconnected()

if __name__ == "__main__":
    pass