import Blazeio as io
from socket import IPPROTO_TCP, TCP_NODELAY

class BlazeioServerProtocol_Config:
    __slots__ = ("srv", "__default_main_handler__",)
    def __init__(app, srv):
        app.srv = srv
        app.srv.add_on_start_callback(app.configure)

    def configure(app):
        app.__default_main_handler__ = app.srv.__main_handler__

class Ciphen:
    __slots__ = ("key",)
    def __init__(app, key: bytes):
        app.key = key

    def encrypt(app, data: bytes):
        return bytes([byte ^ app.key[i % len(app.key)] for i, byte in enumerate(data)])

    def decrypt(app, data: bytes):
        return app.encrypt(data)

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

    @classmethod
    def concat_prts(app, *prts):
        view, where = memoryview(bytearray(sum([len(i) for i in prts]))), 0
        for prt in prts:
            view[where: where + (_len := len(prt))] = prt
            where += _len
        return view

class BlazeioMultiplexer:
    __slots__ = ("__streams__", "__tasks__", "__busy_write__", "__received_size", "__expected_size", "__current_stream_id", "__current_stream", "protocol", "__buff", "__prepends__", "__stream_id_count__", "socket", "__stream_opts", "loop", "_write_buffer_limits", "encrypt_streams", "__io_create_lock__", "__stream_update")
    _data_bounds_ = (
        b"\x00", # sof
        b"\x01", # eof
        b"\x02", # io_eof
        b"\x03", # io_close
        b"\x04", # io_heartbeat
        b"\x05", # io_permission
        b"\x06", # io_create
    )
    
    # b"\x00io_0\x01\x005\x01Hello"

    def __init__(app, protocol, _write_buffer_limits: tuple = (1048576, 256), evloop = None, encrypt_streams = False):
        app.protocol = protocol
        app.encrypt_streams = encrypt_streams
        app.loop = evloop or io.loop
        app._write_buffer_limits = _write_buffer_limits
        app.__streams__ = {}
        app.__tasks__ = []
        app.__stream_id_count__ = 0
        app.__current_stream = None
        app.__buff = bytearray()
        app.__prepends__ = io.deque()
        app.__stream_update = io.SharpEvent(evloop = app.loop)
        app.__busy_write__ = io.ioCondition(evloop = app.loop)
        app.__io_create_lock__ = io.ioCondition(evloop = app.loop)
        app.socket = app.protocol.transport.get_extra_info('socket')
        app.disable_nagle()
        app.update_protocol_write_buffer_limits()
        app.create_task(app.mux())
        app.create_task(app.manage_callbacks())

    def create_task(app, coro):
        app.__tasks__.append(task := app.loop.create_task(coro))
        return task

    def disable_nagle(app):
        app.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)

    def update_protocol_write_buffer_limits(app):
        app.protocol.transport.set_write_buffer_limits(*app._write_buffer_limits)

    def choose_stream(app):
        return app.__prepends__ or app.protocol.__stream__

    def cancel(app):
        for stream in list(app.__streams__):
            app.protocol.stream_closed(app.__streams__[stream])

        for task in app.__tasks__: task.cancel()

    def clear_state(app):
        app.__received_size, app.__expected_size, app.__current_stream_id, app.__current_stream, app.__stream_opts = 0, NotImplemented, NotImplemented, NotImplemented, NotImplemented

    def state(app):
        return Utils.gen_state(app)
    
    def __prepend__(app, data):
        app.__prepends__.appendleft(data)
        app.protocol.__evt__.set()

    def _parse_bounds(app, __buff: (bytes, bytearray, None) = None):
        if __buff is None:
            __buff = app.__buff
        if (idx := __buff.find(app._data_bounds_[0])) == -1 or (idb := __buff.find(app._data_bounds_[1])) == -1: return
        return (idx, idb)

    def _set_stream(app, _point: int = 1):
        if not (bounds := app._parse_bounds()): return None

        if app.__current_stream_id is NotImplemented:
            __current_stream_id, __buff = bytes(memoryview(app.__buff)[bounds[0] + 1:bounds[1]]), app.__buff[bounds[1] + 1:]

            if not (bounds := app._parse_bounds(__buff)): return None

            __stream_opts, __buff = bytes(memoryview(__buff)[bounds[0] + 1:bounds[1]]), __buff[bounds[1] + 1:]

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

    async def enter_stream(app, _id: (None, bytes) = None, instance = None):
        if not instance:
            instance = Stream

        if not _id:
            async with app.__io_create_lock__:
                while (_id := b"io_%X" % app.__stream_id_count__) in app.__streams__:
                    app.__stream_id_count__ += 1
                else:
                    app.__stream_id_count__ += 1

        app.__streams__[_id] = (stream := instance(_id, app))
        return stream

    def metadata(app, _id: (bytes, bytearray), _len: int, __stream_opts: (bytes, bytearray, None) = None):
        return b"%b%b%b%b%b%b%b%X%b" % (app._data_bounds_[0], _id, app._data_bounds_[1], app._data_bounds_[0], __stream_opts or b"", app._data_bounds_[1], app._data_bounds_[0], _len, app._data_bounds_[1])

    def update_stream(app, __current_stream, chunk: (bytes, bytearray)):
        __current_stream.received_size += len(chunk)
        if app.encrypt_streams:
            chunk = Ciphen(__current_stream.id).decrypt(chunk)
        __current_stream.__stream__.append(chunk)
        __current_stream.__evt__.set()

    def perform_checks(app, chunk: (bytes, bytearray)):
        for checker in (app._eof_check, app._stream_closure_check, app._stream_ack):
            if (_ := checker(chunk)) is not None:
                return _

        return None

    def _has_handshake(app):
        return app.__stream_opts == app._data_bounds_[6]

    async def _chunk_received(app, chunk: bytes):
        if app.__current_stream is NotImplemented:
            app.__buff.extend(chunk)

            if not app._set_stream() or not (bounds := app._parse_bounds()):
                return app.__prepend__(chunk)

            app.__expected_size, app.__buff = int(bytes(memoryview(app.__buff)[bounds[0] + 1:bounds[1]]), 16), app.__buff[bounds[1] + 1:]

            remainder, _ = bytes(memoryview(app.__buff)[:]), app.__buff.clear()

            if not (__current_stream := app.__streams__.get(app.__current_stream_id, None)):
                if app._has_handshake():
                    app.__current_stream = await app.protocol.create_stream(app.__current_stream_id)
                else:
                    app.__current_stream = None
            else:
                app.__current_stream = __current_stream

            if app.__stream_opts and app.__stream_opts not in app._data_bounds_:
                app.__current_stream.__stream_opts__.append(app.__stream_opts)

            if app.__current_stream:
                if (_ := app.perform_checks(remainder)) is not None:
                    remainder = _
                app.__current_stream.expected_size += app.__expected_size

            return app.__prepend__(remainder)

        app.__received_size += len(chunk)

        if app.__received_size >= app.__expected_size:
            if app.__received_size > app.__expected_size:
                chunk_size = (len(chunk) - (app.__received_size - app.__expected_size))
                remainder, chunk = bytes(memoryview(chunk)[chunk_size:]), bytes(memoryview(chunk[:chunk_size]))
                app.__prepend__(remainder)

            if app.__current_stream and app.__expected_size and not app.__current_stream.__stream_closed__:
                app.__current_stream.add_callback(app.__current_stream.__send_ack__())
                app.__stream_update.set()

            if app.__current_stream:
                app.update_stream(app.__current_stream, chunk)
            app.clear_state()
        else:
            if app.__current_stream:
                app.update_stream(app.__current_stream, chunk)

    async def __pull__(app):
        while True:
            await app.protocol.ensure_reading()
            while (stream := app.choose_stream()):
                yield stream.popleft()
            else:
                if app.protocol.transport.is_closing():
                    app.cancel()
                    break

    async def mux(app):
        app.clear_state()
        async for chunk in app.__pull__():
            await app._chunk_received(chunk)

    async def batch_handle_callbacks(app, callbacks):
        for stream in callbacks:
            try:
                await stream.wfc()
            except io.CancelledError:
                ...

    async def manage_callbacks(app):
        while True:
            await app.__stream_update.wait_clear()
            if not (callbacks := [stream for stream_id in app.__streams__ if (stream := app.__streams__.get(stream_id)) and stream.__callbacks__]): continue

            (task := app.create_task(app.batch_handle_callbacks(callbacks))).add_done_callback(lambda task: app.__tasks__.remove(task))

class Stream:
    __slots__ = ("protocol", "id", "id_str", "__stream__", "__evt__", "expected_size", "received_size", "eof_received", "_used", "eof_sent", "_close_on_eof", "__prepends__", "transport", "pull", "writer", "chunk_size", "__stream_closed__", "__wait_closed__", "sent_size", "__stream_ack__", "__stream_acks__", "__busy_stream__", "__callbacks__", "__callback_added__", "callback_manager", "__idf__", "__initial_handshake", "__stream_opts__", )

    _chunk_size_base_ = 4096
    def __init__(app, _id: (bytes, bytearray), protocol):
        app.clear_state()
        app.protocol = protocol
        app.transport = app.protocol.protocol.transport
        app.id = _id
        app.__stream_closed__ = False
        app.__initial_handshake = app.protocol._data_bounds_[6]
        app.pull = app.__pull__
        app.writer = app.__writer__
        app.chunk_size = app.calculate_chunk_size()
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
        app.__busy_stream__.lock()
        #app.callback_manager = io.loop.create_task(app.manage_callbacks())

    def calculate_chunk_size(app):
        if ((chunk_size := int(len(app.protocol.protocol.__buff__)/5)) < app._chunk_size_base_*4) or (chunk_size > app._chunk_size_base_*7):
            chunk_size = app._chunk_size_base_

        return chunk_size

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
        if app.protocol.encrypt_streams:
            data = Ciphen(app.id).encrypt(data)

        if app.can_write():
            if app.__initial_handshake:
                __stream_opts = __stream_opts or app.__initial_handshake
                app.__initial_handshake = None
            
            if not isinstance(data, bytes):
                data = bytes(data)

            return app.transport.write(app.protocol.metadata(app.id, len(data), __stream_opts) + data)
        else:
            raise app.protocol.protocol.__stream_closed_exception__()

    def can_write(app):
        if app.transport.is_closing() or app.__stream_closed__: return False
        return True

    def stream_closed(app):
        app.__stream_closed__ = True
        for event in (app.__wait_closed__, app.__callback_added__, app.__stream_ack__,): event.set()
    
    def check_busy_stream(app):
        if app.__busy_stream__.locked() and app.__busy_stream__.initial:
            app.__busy_stream__.initial = False
            app.__busy_stream__.release()

    async def wfc(app):
        while app.__callbacks__:
            await app.__callbacks__.popleft()

    async def manage_callbacks(app):
        while True:
            await app.__callback_added__.wait_clear()
            await app.wfc()
            if app.__stream_closed__: break

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

    def __await__(app):
        app.check_busy_stream()
        yield from app.ensure_reading().__await__()
        __stream__ = app.choose_stream()
        return __stream__.popleft() if __stream__ else None

    async def __pull__(app):
        app.check_busy_stream()
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
        if not app.__stream_acks__:
            await app.__stream_ack__.wait_clear()

        if app.__stream_acks__:
            app.__stream_acks__.popleft()
        else:
            raise app.protocol.protocol.__stream_closed_exception__()

    async def __writer__(app, data: (bytes, bytearray), add: bool = True, wait: bool = True, __stream_opts: (bytes, bytearray, None) = None):
        if not data: return
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
        if app.__stream_closed__: return
        async with app.__busy_stream__:
            pass

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

class Blazeio_Stream_Server(Stream, io.BlazeioPayloadUtils, io.ExtraToolset):
    def __init__(app, *args):
        Stream.__init__(app, *args)
        io.ServerProtocolEssentials.defaults(app)
        app.request, app.writer, app.pull = app.__pull__, app.__writer__, app.__pull__

class Blazeio_Stream_Client(Stream,):
    def __init__(app, *args):
        Stream.__init__(app, *args)
        app.__timeout__ = None
        app.cancel_on_disconnect = True
        app.push, app.write = app.writer, app.writer

def BlazeioMuxProtocol(base_class=object):
    class _BlazeioMuxProtocol(base_class):
        __slots__ = ()
        def __initialize__(app):
            app.connection_made_evt = io.SharpEvent(evloop = app.__evt__.loop)

        def connection_made(app, transport):
            transport.pause_reading()
            app.transport = transport
            app.multiplexer = BlazeioMultiplexer(app)
            app.connection_made_evt.set()

        def stream_closed(app, stream):
            app.multiplexer.__streams__.pop(stream.id, None)
            stream.stream_closed()

        def accept(app, *args):
            return app.create_stream(*args)

        def cancel(app):
            app.multiplexer.cancel()
            app.close()

        def connection_lost(app, exc):
            app.__evt__.set()
            app.__overflow_evt__.set()
            app.cancel()

    return _BlazeioMuxProtocol

class BlazeioClientProtocol(BlazeioMuxProtocol(io.BlazeioClientProtocol)):
    __slots__ = ("multiplexer", "connection_made_evt")
    __stream_closed_exception__ = io.ServerDisconnected

    def __getattr__(app, name):
        return getattr(app.multiplexer, name)

    async def create_stream(app, _id: (None, bytes) = None):
        if not app.connection_made_evt.is_set():
            await app.connection_made_evt.wait()
        if app.transport.is_closing():
            raise app.__stream_closed_exception__

        return await app.multiplexer.enter_stream(_id, Blazeio_Stream_Client)

    def close(app):
        app.transport.close()

class BlazeioServerProtocol(BlazeioMuxProtocol(io.BlazeioServerProtocol)):
    __slots__ = ("multiplexer", "connection_made_evt")
    __stream_closed_exception__ = io.ClientDisconnected

    async def create_stream(app, _id):
        app.multiplexer.__tasks__.append(task := io.loop.create_task(app.__transporter__(r := await app.multiplexer.enter_stream(_id, Blazeio_Stream_Server))))
        task.__BlazeioProtocol__ = r
        return r

    async def __transporter__(app, r):
        try:
            await app.on_client_connected(r)
            await r.eof()
        except GeneratorExit: ...
        except StopIteration: ...
        finally:
            await r.__eof__()
            await r.__close__()

    @classmethod
    def configure_server(app, web):
        return BlazeioServerProtocol_Config(web)

Protocols = io.Dot_Dict(server = BlazeioServerProtocol, client = BlazeioClientProtocol)

if __name__ == "__main__": ...