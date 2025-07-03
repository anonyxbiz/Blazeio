import Blazeio as io
from socket import IPPROTO_TCP, TCP_NODELAY

class Utils:
    @classmethod
    def _to_state(cls, app):
        if hasattr(app.__class__, "__slots__"):
            _keys, _get_key = app.__class__.__slots__, lambda key: getattr(app, key, "")
        else:
            if hasattr(app, "__dict__"):
                _keys, _get_key = list(app.__dict__.keys()), lambda key: app.__dict__.get(key, "")

            elif isinstance(app, dict):
                _keys, _get_key = list(app.keys()), lambda key: app.get(key, "")

        return {key: str(value)[:500] if not isinstance(value := _get_key(key), (int, str, dict)) else value for key in _keys}

    @classmethod
    def gen_state(cls, app):
        _state = cls._to_state(app)

        for key in list(_state.keys()):
            if isinstance(val := _state.get(key), dict):
                _state[key] = cls._to_state(val)

        return _state

class BlazeioMultiplexer:
    __slots__ = ("__streams__", "__tasks__", "__busy_write__", "__received_size", "__expected_size", "__current_stream_id", "__current_stream", "protocol", "__buff", "__prepends__", "__stream_id_count__", "socket", "__stream_created_evt__", "__stream_opts")
    _data_bounds_ = (b"<::", b"::>", b"<-io_eof->", b"<-io_close->", b"", b"<-io_ack->", b"<-create_stream->")
    
    _write_buffer_limit = 1024*1024

    def __init__(app, protocol):
        app.protocol = protocol
        app.__streams__ = {}
        app.__tasks__ = []
        app.__stream_id_count__ = 0
        app.__current_stream = None
        app.__buff = bytearray()
        app.__prepends__ = io.deque()
        app.__busy_write__ = io.ioCondition(evloop = io.loop)
        app.__stream_created_evt__ = io.SharpEvent(evloop = io.loop)
        app.socket = app.protocol.transport.get_extra_info('socket')
        app.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        app.update_protocol_write_buffer_limits()
        app.__tasks__.append(io.loop.create_task(app.update_streams()))

    def update_protocol_write_buffer_limits(app):
        app.protocol.transport.set_write_buffer_limits(app._write_buffer_limit, 0)

    def choose_stream(app):
        return app.__prepends__ or app.protocol.__stream__

    def cancel(app):
        for task in app.__tasks__: task.cancel()
        app.protocol.cancel()

    def clear_state(app):
        app.__received_size, app.__expected_size, app.__current_stream_id, app.__current_stream, app.__stream_opts = 0, NotImplemented, NotImplemented, NotImplemented, NotImplemented

    def state(app):
        return Utils.gen_state(app)

    def _parse_bounds(app, __buff: (bytes, bytearray, None) = None):
        if __buff is None:
            __buff = app.__buff

        if (idx := __buff.find(app._data_bounds_[0])) == -1 or (idb := __buff.find(app._data_bounds_[1])) == -1: return
        return (idx, idb)

    def _set_stream(app, _point: int = 1):
        if not (bounds := app._parse_bounds()): return None

        if app.__current_stream_id is NotImplemented:
            __current_stream_id, __buff = bytes(memoryview(app.__buff)[:bounds[1] + len(app._data_bounds_[_point])]), app.__buff[bounds[1] + len(app._data_bounds_[_point]):]

            if not (bounds := app._parse_bounds(__buff)): return None

            __stream_opts, __buff = bytes(memoryview(__buff)[bounds[0] + len(app._data_bounds_[0]):bounds[1]]), __buff[bounds[1] + len(app._data_bounds_[_point]):]

            app.__current_stream_id, app.__buff, app.__stream_opts = __current_stream_id, __buff, __stream_opts

        return True

    def _eof_check(app, chunk, _point: int = 2):
        if app.__stream_opts == app._data_bounds_[_point]:
            opts, remainder = memoryview(chunk)[:app.__expected_size], memoryview(chunk)[app.__expected_size:]
            app.__expected_size -= len(opts)
            app.__current_stream.eof_received = True
            return bytes(remainder)

        return None

    def _stream_closure_check(app, chunk, _point: int = 3):
        if app.__stream_opts == app._data_bounds_[_point]:
            opts, remainder = memoryview(chunk)[:app.__expected_size], memoryview(chunk)[app.__expected_size:]
            app.__expected_size -= len(opts)
            app.protocol.stream_closed(app.__current_stream)
            return bytes(remainder)

        return None

    def _stream_ack(app, chunk, _point: int = 5):
        if app.__stream_opts == app._data_bounds_[_point]:
            opts, remainder = memoryview(chunk)[:app.__expected_size], memoryview(chunk)[app.__expected_size:]
            app.__expected_size -= len(opts)
            app.__current_stream.__stream_acks__.append(bytes(opts))
            app.__current_stream.__stream_ack__.set()
            return bytes(remainder)

        return None

    def stream_id_gen(app):
        _id = app.__stream_id_count__
        app.__stream_id_count__ += 1
        return b"%bio_%X%b" % (app._data_bounds_[0], _id, app._data_bounds_[1])

    def enter_stream(app, _id: (None, bytes) = None, instance = None):
        if not instance:
            instance = Stream

        if not _id:
            _id = app.stream_id_gen()

        app.__streams__[_id] = (stream := instance(_id, app))

        return stream

    def metadata(app, _id: (bytes, bytearray), _len: int, __stream_opts: (bytes, bytearray, None) = None):
        return b"%b%b%b%X%b" % (_id, app._data_bounds_[0] + (__stream_opts or b"") + app._data_bounds_[1], app._data_bounds_[0], _len, app._data_bounds_[1])

    def update_stream(app, __current_stream, chunk: (bytes, bytearray)):
        __current_stream.received_size += len(chunk)
        __current_stream.__stream__.append(chunk)
        __current_stream.__evt__.set()

    async def __pull__(app):
        while True:
            await app.protocol.ensure_reading()
            while (stream := app.choose_stream()):
                yield stream.popleft()
            else:
                if app.protocol.transport.is_closing():
                    app.cancel()
                    break

    def perform_checks(app, chunk: (bytes, bytearray)):
        for checker in (app._eof_check, app._stream_closure_check, app._stream_ack):
            if (_ := checker(chunk)) is not None:
                return _

        return None
    
    def _has_handshake(app):
        return app.__stream_opts == app._data_bounds_[6]

    async def update_streams(app):
        app.clear_state()
        async for chunk in app.__pull__():
            if app.__current_stream is NotImplemented:
                app.__buff.extend(chunk)

                if not app._set_stream(): continue

                if not (bounds := app._parse_bounds()): continue

                app.__expected_size, app.__buff = int(bytes(memoryview(app.__buff)[bounds[0] + len(app._data_bounds_[0]):bounds[1]]), 16), app.__buff[bounds[1] + len(app._data_bounds_[1]):]

                chunk, _ = bytes(memoryview(app.__buff)[:]), app.__buff.clear()
                
                if not (__current_stream := app.__streams__.get(app.__current_stream_id, None)):
                    if app._has_handshake():
                        __current_stream = app.protocol.create_stream(app.__current_stream_id)
                    else:
                        __current_stream = None

                app.__current_stream = __current_stream

                if app.__stream_opts and app.__stream_opts not in app._data_bounds_:
                    app.__current_stream.__stream_opts__.append(app.__stream_opts)

                if app.__current_stream:
                    if (_ := app.perform_checks(chunk)) is not None:
                        chunk = _
    
                    app.__current_stream.expected_size += app.__expected_size

            app.__received_size += len(chunk)

            if app.__received_size >= app.__expected_size:
                if app.__received_size > app.__expected_size:
                    chunk_size = (len(chunk) - (app.__received_size - app.__expected_size))
                    remainder, chunk = bytes(memoryview(chunk)[chunk_size:]), bytes(memoryview(chunk[:chunk_size]))
                    app.__prepends__.appendleft(remainder)

                if app.__current_stream and app.__expected_size and not app.__current_stream.__stream_closed__:
                    app.__current_stream.add_callback(app.__current_stream.__send_ack__())

                if app.__current_stream:
                    app.update_stream(app.__current_stream, chunk)
                app.clear_state()
            else:
                if app.__current_stream:
                    app.update_stream(app.__current_stream, chunk)

class Stream:
    __slots__ = ("protocol", "id", "id_str", "__stream__", "__evt__", "expected_size", "received_size", "eof_received", "_used", "eof_sent", "_close_on_eof", "__prepends__", "transport", "pull", "writer", "chunk_size", "__stream_closed__", "__wait_closed__", "sent_size", "__stream_ack__", "__stream_acks__", "__busy_stream__", "__callbacks__", "__callback_added__", "callback_manager", "__idf__", "__initial_handshake", "__stream_opts__")
    
    _chunk_size_base_ = 4096*4

    def __init__(app, _id: (bytes, bytearray), protocol):
        app.clear_state()
        app.protocol = protocol
        app.transport = app.protocol.protocol.transport
        app.id = _id
        app.__stream_closed__ = False
        app.__initial_handshake = app.protocol._data_bounds_[6]
        app.pull = app.__pull__
        app.writer = app.__writer__
        app.chunk_size = app._chunk_size_base_
        app.id_str = app.id.decode()
        app.__stream__ = io.deque()
        app.__prepends__ = io.deque()
        app.__stream_acks__ = io.deque()
        app.__callbacks__ = io.deque()
        app.__stream_opts__ = []
        app.__evt__ = io.SharpEvent(False, evloop = io.loop)
        app.__callback_added__ = io.SharpEvent(False, evloop = io.loop)
        app.__wait_closed__ = io.SharpEvent(False, evloop = io.loop)
        app.__stream_ack__ = io.SharpEvent(False, evloop = io.loop)
        app.__busy_stream__ = io.ioCondition(evloop = io.loop)
        app.callback_manager = io.loop.create_task(app.manage_callbacks())

    def id_f(app):
        if not hasattr(app, "__idf__"):
            app.__idf__ = "%s%s|%s" % (app.id_str[:3], app.__class__.__name__, app.id_str[3:])

        return app.__idf__

    def clear_state(app):
        app.received_size, app.sent_size, app.expected_size, app.eof_received, app._used, app.eof_sent, app._close_on_eof = 0, 0, 0, False, False, False, True

    def state(app):
        return Utils.gen_state(app)

    def choose_stream(app):
        return app.__prepends__ or app.__stream__

    def prepend(app, data):
        app.__prepends__.appendleft(data)
        app.__evt__.set()

    def add_callback(app, cb):
        app.__callbacks__.append(cb)
        app.__callback_added__.set()

    def write_mux(app, data, __stream_opts):
        if app.can_write():
            if app.__initial_handshake:
                __stream_opts = __stream_opts or app.__initial_handshake
                app.__initial_handshake = None

            return app.transport.write(app.protocol.metadata(app.id, len(data), __stream_opts) + bytes(data))
        else:
            raise app.protocol.protocol.__stream_closed_exception__()

    def can_write(app):
        if app.transport.is_closing() or app.__stream_closed__: return False
        return True

    def stream_closed(app):
        app.__stream_closed__ = True
        for event in (app.__wait_closed__, app.__callback_added__, app.__stream_ack__,): event.set()

    async def wfc(app):
        while app.__callbacks__:
            await app.__callbacks__.popleft()

    async def manage_callbacks(app):
        while True:
            await app.__callback_added__.wait_clear()
            if app.__stream_closed__: break
            await app.wfc()

    async def __aenter__(app):
        if app._used:
            app.clear_state()
        return app

    async def __aexit__(app, exc_t, exc_v, tb):
        if app._used and not app.eof_sent:
            await app.__eof__()

        return False

    async def ensure_reading(app):
        if not app.choose_stream():
            if not app.__stream_closed__:
                await app.__evt__.wait_clear()

    async def __pull__(app):
        while True:
            await app.ensure_reading()
            async with app.__busy_stream__:
                while (__stream__ := app.choose_stream()) and (chunk := __stream__.popleft()):
                    yield chunk
                else:
                    if app.eof_received and not app.choose_stream(): return

                    if app.__stream_closed__ and not app.choose_stream():
                        await app.__close__()
                        return

    async def __to_chunks__(app, data: memoryview):
        while len(data) > app.chunk_size:
            chunk, data = data[:app.chunk_size], data[app.chunk_size:]
            yield chunk

        yield data

    async def wfa(app):
        while not app.__stream_acks__:
            await app.__stream_ack__.wait_clear()

        if app.__stream_acks__:
            app.__stream_acks__.popleft()

    async def __writer__(app, data: (bytes, bytearray), add: bool = True, wait: bool = True, __stream_opts: (bytes, bytearray, None) = None):
        if not app.can_write(): raise app.protocol.protocol.__stream_closed_exception__()

        if not app._used: app._used = True

        async for chunk in app.__to_chunks__(memoryview(data)):
            async with app.protocol.__busy_write__:
                await app.protocol.protocol.buffer_overflow_manager()
                app.write_mux(chunk, __stream_opts)

            if wait:
                await app.wfa()

        if add:
            app.sent_size += len(data)

    async def read_data(app, decode: bool = False):
        _ = bytearray()
        async for chunk in app.__pull__():
            _.extend(chunk)
        return _.decode() if decode else _

    async def __send_ack__(app):
        async with app.__busy_stream__: pass
        if app.can_write(): await app.__writer__(app.protocol._data_bounds_[4], False, False, app.protocol._data_bounds_[5])

    async def __eof__(app, data: (None, bytes, bytearray) = None):
        if data and app.can_write(): await app.__writer__(data)

        if app.eof_sent: return

        if app.can_write():
            app.eof_sent = True
            return await app.__writer__(app.protocol._data_bounds_[4], False, False, app.protocol._data_bounds_[2])

    async def __close__(app, __stream_closed__: bool = False):
        if not __stream_closed__ and app.can_write():
            await app.__writer__(app.protocol._data_bounds_[4], False, False, app.protocol._data_bounds_[3])

        if not app.__stream_closed__:
            app.protocol.protocol.stream_closed(app)

class Stream_Server(Stream, io.BlazeioPayloadUtils, io.ExtraToolset):
    def __init__(app, *args):
        Stream.__init__(app, *args)
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
        app.cancel_on_disconnect = True
        app.request, app.writer = app.__pull__, app.__writer__

class Stream_Client(Stream,):
    def __init__(app, *args):
        Stream.__init__(app, *args)
        app.__timeout__ = None
        app.cancel_on_disconnect = True
        app.push, app.write = app.writer, app.writer

class BlazeioClientProtocol(io.BlazeioClientProtocol):
    __slots__ = ("multiplexer",)
    __stream_closed_exception__ = io.ServerDisconnected

    def __getattr__(app, name):
        return getattr(app.multiplexer, name)

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.multiplexer = BlazeioMultiplexer(app)

    def cancel(app):
        for task in app.multiplexer.__tasks__: task.cancel()
        app.transport.close()

    def create_stream(app, _id: (None, bytes) = None):
        return app.multiplexer.enter_stream(_id, Stream_Client)

    def stream_closed(app, stream):
        app.multiplexer.__streams__.pop(stream.id, None)
        stream.stream_closed()

    def accept(app, *args): return app.create_stream(*args)

class BlazeioServerProtocol(io.BlazeioServerProtocol):
    __slots__ = ("multiplexer", "transport")
    __stream_closed_exception__ = io.ClientDisconnected

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.multiplexer = BlazeioMultiplexer(app)

    def create_stream(app, _id):
        app.multiplexer.__tasks__.append(task := io.loop.create_task(app.__transporter__(r := app.multiplexer.enter_stream(_id, Stream_Server))))

        task.__BlazeioServerProtocol__ = r
        return r

    def stream_closed(app, stream):
        app.multiplexer.__streams__.pop(stream.id, None)
        stream.stream_closed()

    async def __transporter__(app, r):
        try:
            await app.on_client_connected(r)
        finally:
            await r.__eof__()
            await r.__close__()

    def cancel(app):
        for task in app.multiplexer.__tasks__: task.cancel()
        app.close()
    
    def accept(app, *args): return app.create_stream(*args)

if __name__ == "__main__":
    pass
