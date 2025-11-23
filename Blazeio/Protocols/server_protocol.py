from ..Dependencies.alts import *
from .server_protocol_extratools import *

class BlazeioPayloadUtils:
    __slots__ = ()
    async def transporter(app):
        await app.on_client_connected(app)
        app.close()

    def control(app, duration=0):
        return sleep(duration)

    def close(app):
        app.transport.close()

class BlazeioServerProtocol(BlazeioProtocol, BufferedProtocol, BlazeioPayloadUtils, ExtraToolset):
    __slots__ = ('on_client_connected','__stream__','__is_buffer_over_high_watermark__','__is_at_eof__','__is_alive__','transport','method','tail','path','headers','__is_prepared__','__status__','content_length','current_length','__perf_counter__','ip_host','ip_port','identifier','__prepared_headers__','__miscellaneous__','__timeout__','__buff__','__buff__memory__','store','transfer_encoding','pull','write','encoder','encoder_obj','__evt__','__overflow_evt__','cancel', 'cancel_on_disconnect',)
    non_bodied_methods = ("GET", "HEAD", "OPTIONS", "DELETE")
    no_response_body_methods = ("HEAD",)
    def __init__(app, on_client_connected, evloop, INBOUND_CHUNK_SIZE=None):
        app.on_client_connected = on_client_connected
        app.__buff__ = bytearray(INBOUND_CHUNK_SIZE)
        app.__stream__ = deque()
        app.__buff__memory__ = memoryview(app.__buff__)
        app.cancel_on_disconnect = True
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
        app.__prepared_headers__ = None
        app.pull = None
        app.__miscellaneous__ = None
        app.store = None
        app.__timeout__ = None
        app.__evt__ = SharpEvent(evloop = evloop)
        app.__overflow_evt__ = SharpEvent(evloop = evloop)
        app.__initialize__()

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.cancel = (task := loop.create_task(app.transporter())).cancel
        task.__BlazeioProtocol__ = app

    def abort_connection(app):
        if app.cancel and app.cancel_on_disconnect:
            app.cancel()
        raise ClientDisconnected(origin = "abort_connection")

    def state(app):
        return {key: str(value)[:500] if not isinstance(value := getattr(app, key, ""), (int, str)) else value for key in app.__class__.__slots__}

    def request(app, *args, **kwargs):
        return app.__aiter__(*args, **kwargs)

    async def writer(app, data: (bytes, bytearray)):
        if not app.__is_prepared__:
            app.__is_prepared__ = True
        await app.buffer_overflow_manager()

        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise ClientDisconnected()

class Httpkeepalive:
    __slots__ = ("web", "after_middleware", "__default_handler__", "timeout", "_max", "keepalive_headers")
    def __init__(app, web: (None, Utype,), after_middleware: (None, Utype) = None, __default_handler__: (None, Utype) = None, timeout: (int, Utype) = 60*60*5, _max: (int, Utype) = 1000**2):
        set_from_args(app, locals(), Utype)
        if not app.after_middleware:
            if (after_middleware := app.web.declared_routes.pop("after_middleware", None)):
                app.after_middleware = after_middleware.get("func")

        app.configure()

    def configure(app):
        if app.web.__main_handler__ is not NotImplemented:
            app.__default_handler__ = app.web.__main_handler__

        app.keepalive_headers = (
            b"Connection: Keep-Alive\r\n"
            b"Keep-Alive: timeout=%d, max=%d\r\n" % (app.timeout, app._max)
        )

    def get_handler(app):
        return app.__default_handler__ or app.web.__default_handler__

    async def __main_handler__(app, r):
        while not r.transport.is_closing():
            exc = None
            try:
                r += app.keepalive_headers
                await app.get_handler()(r)
            except Abort as e:
                await e.text(r)
            except (Eof, ServerGotInTrouble, BrokenPipeError):
                ...
            except (CancelledError, KeyboardInterrupt, CloseConnection, ClientDisconnected, ServerDisconnected):
                raise
            except Exception as e:
                exc = e
            finally:
                if r.__is_prepared__:
                    await r.eof()
                else:
                    await Abort("Server Got In Trouble", 500).text(r)

                if app.after_middleware: await app.after_middleware(r)

                if exc:
                    await traceback_logger(exc, frame = 4)

                ServerProtocolEssentials.reset(r)

if __name__ == "__main__": ...