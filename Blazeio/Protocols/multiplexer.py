import Blazeio as io
from socket import IPPROTO_TCP, TCP_NODELAY

class BlazeioMultiplexerConf:
    conf = io.ddict(protocol = io.ddict(_write_buffer_limits = (1048576, 0), encrypt_streams = False))

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
        if not isinstance(app.key, bytes):
            app.key = app.key.encode()

    def encrypt(app, data: bytes):
        return bytes([byte ^ app.key[i % len(app.key)] for i, byte in enumerate(data)])

    def decrypt(app, data: bytes):
        return app.encrypt(data)

class Utils:
    @classmethod
    def gen_state(cls, app):
        return {key: str(value) if not isinstance(value := getattr(app, key, ""), (int, str, dict)) else value for key in app.__class__.__slots__}

    @classmethod
    def concat_prts(app, *prts):
        view, where = memoryview(bytearray(sum([len(i) for i in prts]))), 0
        for prt in prts:
            view[where: where + (_len := len(prt))] = prt
            where += _len
        return view

class BlazeioMultiplexer:
    __slots__ = ("__streams__", "__tasks__", "__busy_write__", "__received_size", "__expected_size", "__current_stream_id", "__current_stream", "protocol", "__buff", "__prepends__", "__stream_id_count__", "socket", "__stream_opts", "loop", "_write_buffer_limits", "encrypt_streams", "__io_create_lock__", "__stream_update", "perf_analytics", "analytics", "__current_sid",)
    _data_bounds_ = (
        b"\x00", # sof
        b"\x01", # eof
        b"\x02", # io_eof
        b"\x03", # io_close
        b"\x04", # io_heartbeat
        b"\x05", # io_permission
        b"\x06", # io_create
    )

    _min_buff_size_ = 1024*100

    def __init__(app, protocol: io.BlazeioProtocol, evloop: any = None, _write_buffer_limits: tuple = (1048576, 0), encrypt_streams: bool = False, perf_analytics: bool = True):
        app.protocol = protocol
        app.encrypt_streams = encrypt_streams
        app.loop = evloop or io.loop
        app.perf_analytics = perf_analytics
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
        app.check_buff()
        app.init_analytics()
        app.create_task(app.mux())

    def init_analytics(app):
        if not app.perf_analytics: return
        app.analytics = io.ddict(enter_stream = io.ddict(total_enter_stream_durations = 0.0, streams = 0), transfer_rate = io.ddict(bytes_transferred = 0.0), start_time = io.perf_counter())
    
    def transport_writer(app, _id: bytes, sid: (bytes, None), __stream_opts: bytes, data: bytes):
        if app.encrypt_streams:
            data = Ciphen(_id).encrypt(data)

        app.protocol.transport.write(app.metadata(_id, sid, len(data), __stream_opts) + data)
        return sid

    def check_buff(app):
        if len(app.protocol.__buff__) < app._min_buff_size_:
            app.protocol.__buff__ = bytearray(app._min_buff_size_)
            app.protocol.__buff__memory__ = memoryview(app.protocol.__buff__)

    def create_task(app, coro):
        app.__tasks__.append(task := app.loop.create_task(coro))
        return task

    def disable_nagle(app):
        app.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)

    def update_protocol_write_buffer_limits(app):
        app.protocol.transport.set_write_buffer_limits(*app._write_buffer_limits)

    def choose_stream(app):
        return app.protocol.__stream__ or app.__prepends__

    def cancel(app):
        for stream in list(app.__streams__):
            app.protocol.stream_closed(app.__streams__[stream])
        for task in app.__tasks__: task.cancel()

    def clear_state(app):
        app.__received_size, app.__expected_size, app.__current_stream_id, app.__current_stream, app.__stream_opts, app.__current_sid = 0, NotImplemented, NotImplemented, NotImplemented, NotImplemented, NotImplemented

    def calc_analytics(app):
        if not app.perf_analytics: return
        app.analytics.transfer_rate.mb_per_sec = ((app.analytics.transfer_rate.bytes_transferred/1024**2)/(io.perf_counter() - app.analytics.start_time))
        app.analytics.streams_per_second = (app.analytics.enter_stream.streams/(app.analytics.enter_stream.total_enter_stream_durations/app.analytics.enter_stream.streams))
        app.analytics = app.analytics

    def state(app):
        app.calc_analytics()
        return Utils.gen_state(app)
    
    def __prepend__(app, data, wakeup = False, clear = True):
        if clear:
            app.__buff.clear()

        app.__prepends__.appendleft(data)
        if wakeup: app.protocol.__evt__.set()

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
            app.__current_stream.__stream_acks__[bytes(opts)] = True
            app.__current_stream.__stream_ack__.set()
            return bytes(remainder)
        return None

    async def enter_stream(app, _id: (None, bytes) = None, instance = None):
        if app.perf_analytics:
            start_time = io.perf_counter()
        if not instance:
            instance = Stream

        if not _id:
            async with app.__io_create_lock__:
                while (_id := b"io_%d" % app.__stream_id_count__) in app.__streams__:
                    app.__stream_id_count__ += 1
                else:
                    app.__stream_id_count__ += 1

        app.__streams__[_id] = (stream := instance(_id, app))

        if app.perf_analytics:
            app.analytics.enter_stream.total_enter_stream_durations += (io.perf_counter() - start_time)
            app.analytics.enter_stream.streams += 1

        return stream

    def metadata(app, _id: bytes, sid: bytes, _len: int, __stream_opts: (bytes, None) = None):
        return b"%b%b%b%b%b%b%b%b%b%b%X%b" % (app._data_bounds_[0], _id, app._data_bounds_[1], app._data_bounds_[0], __stream_opts or b"", app._data_bounds_[1], app._data_bounds_[0], sid or b"", app._data_bounds_[1], app._data_bounds_[0], _len, app._data_bounds_[1])

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
                return app.__prepend__(chunk, clear = False)

            app.__current_sid, app.__buff = bytes(memoryview(app.__buff)[bounds[0] + 1:bounds[1]]), app.__buff[bounds[1] + 1:]

            if not (bounds := app._parse_bounds()):
                return app.__prepend__(chunk, clear = False)

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
                else:
                    app.__current_stream.add_callback(app.__current_stream.__send_ack__(app.__current_sid))

                app.__current_stream.expected_size += app.__expected_size

            return app.__prepend__(remainder, wakeup = True)

        app.__received_size += len(chunk)

        if app.__received_size >= app.__expected_size:
            if app.__received_size > app.__expected_size:
                chunk_size = (len(chunk) - (app.__received_size - app.__expected_size))
                remainder, chunk = bytes(memoryview(chunk)[chunk_size:]), bytes(memoryview(chunk[:chunk_size]))
                app.__prepend__(remainder)

            if app.__current_stream and not app.__current_stream.__stream_closed__:
                app.__stream_update.set()

            if app.__current_stream:
                # if app.__current_sid: app.__current_stream.add_callback(app.__current_stream.__send_ack__(app.__current_sid))
                app.update_stream(app.__current_stream, chunk)

            app.clear_state()
        else:
            if app.__current_stream:
                # if app.__current_sid: app.__current_stream.add_callback(app.__current_stream.__send_ack__(app.__current_sid))
                app.update_stream(app.__current_stream, chunk)

    async def __pull__(app):
        while True:
            await app.protocol.ensure_reading()
            while (stream := app.choose_stream()):
                chunk = stream.popleft()
                if app.__prepends__:
                    chunk = app.__prepends__.popleft() + chunk

                yield chunk
            else:
                if app.protocol.transport.is_closing():
                    app.cancel()
                    break

    async def mux(app):
        app.clear_state()
        async for chunk in app.__pull__():
            if app.perf_analytics: app.analytics.transfer_rate.bytes_transferred += len(chunk)
            await app._chunk_received(chunk)

class Stream:
    __slots__ = ("protocol", "id", "id_str", "__stream__", "__evt__", "expected_size", "received_size", "eof_received", "_used", "eof_sent", "_close_on_eof", "__prepends__", "transport", "pull", "writer", "chunk_size", "__stream_closed__", "__wait_closed__", "sent_size", "__stream_ack__", "__stream_acks__", "__busy_stream__", "__callbacks__", "__callback_added__", "callback_manager", "__idf__", "__initial_handshake", "__stream_opts__", "sids")

    _chunk_size_base_ = 4096
    def __init__(app, _id: (bytes, bytearray), protocol):
        app.clear_state()
        app.protocol = protocol
        app.transport = app.protocol.protocol.transport
        app.id = _id
        app.__stream_closed__ = False
        app.__initial_handshake = app.protocol._data_bounds_[6]
        app.sids = 0
        app.pull = app.__pull__
        app.writer = app.__writer__
        app.chunk_size = app.calculate_chunk_size()
        app.id_str = app.id.decode()
        app.__stream__ = io.deque()
        app.__prepends__ = io.deque()
        app.__stream_acks__ = {}
        app.__callbacks__ = io.deque()
        app.__stream_opts__ = []
        app.__evt__ = io.SharpEvent(False, evloop = io.loop)
        app.__callback_added__ = io.SharpEvent(False, evloop = io.loop)
        app.__wait_closed__ = io.SharpEvent(False, evloop = io.loop)
        app.__stream_ack__ = io.SharpEvent(False, evloop = io.loop)
        app.__busy_stream__ = io.ioCondition(evloop = io.loop)
        # app.__busy_stream__.lock()
        app.callback_manager = io.loop.create_task(app.manage_callbacks())

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

    def gen_sid(app):
        sid = b"%d" % app.sids
        app.sids += 1
        return sid

    def write_mux(app, data, __stream_opts, gen_sid):
        if app.can_write():
            if app.__initial_handshake:
                __stream_opts = __stream_opts or app.__initial_handshake
                app.__initial_handshake = None

            return app.protocol.transport_writer(app.id, app.gen_sid() if gen_sid else None, __stream_opts, data)
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
        try:
            while True:
                if len(app.__stream__) >= 10:
                    await app.__busy_stream__.acquire()
                else:
                    if app.__busy_stream__.locked():
                        app.__busy_stream__.release()
                
                await app.ensure_reading()

                while (__stream__ := app.choose_stream()) and (chunk := __stream__.popleft()):
                    # async with app.__busy_stream__:
                    yield chunk
                else:
                    if app.eof_received and not app.choose_stream():
                        return
                    if app.__stream_closed__ and not app.choose_stream():
                        await app.__close__()
                        return
        finally:
            app.__busy_stream__.lock()

    async def __to_chunks__(app, data: memoryview):
        while len(data) > app.chunk_size:
            chunk, data = data[:app.chunk_size], data[app.chunk_size:]
            yield chunk

        yield data

    async def wfa(app, sid: bytes):
        # if io.debug_mode: await io.plog.yellow(app.id_str, sid, "waiting for sid...")
        while not sid in app.__stream_acks__:
            await app.__stream_ack__.wait_clear()

        if sid in app.__stream_acks__:
            app.__stream_acks__.pop(sid)
            # if io.debug_mode: await io.plog.green(app.id_str, sid, "gotten sid...")
        else:
            raise app.protocol.protocol.__stream_closed_exception__()

    async def __writer__(app, data: (bytes, bytearray), add: bool = True, wait: bool = True, __stream_opts: (bytes, bytearray, None) = None):
        if not data: return
        if not app.can_write(): raise app.protocol.protocol.__stream_closed_exception__()

        if not app._used: app._used = True

        async for chunk in app.__to_chunks__(memoryview(data)):
            async with app.protocol.__busy_write__:
                await app.protocol.protocol.buffer_overflow_manager()
                sid = app.write_mux(chunk, __stream_opts, gen_sid = wait)

            if wait:
                await app.wfa(sid)

        if add:
            app.sent_size += len(data)

    async def read_data(app, decode: bool = False):
        _ = bytearray()
        async for chunk in app.__pull__():
            _.extend(chunk)
        return _.decode() if decode else _

    async def __send_ack__(app, sid: bytes):
        if app.__stream_closed__: return
        async with app.__busy_stream__: ...

        if app.can_write(): await app.__writer__(sid, False, False, app.protocol._data_bounds_[5])

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
        app.request, app.writer, app.pull = app.__pull__, app.__writer__, None

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
            app.multiplexer = BlazeioMultiplexer(app, app.__evt__.loop, **BlazeioMultiplexerConf.conf.protocol)
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
        try:
            if hasattr(app, "multiplexer"):
                return getattr(app.multiplexer, name)
            else:
                raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))
        except RecursionError:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

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

class _Protocols:
    def __init__(app):
        BlazeioMultiplexerConf.conf.server = BlazeioServerProtocol
        BlazeioMultiplexerConf.conf.client = BlazeioClientProtocol

    def __getattr__(app, key):
        return BlazeioMultiplexerConf.conf.__getattr__(key)

    def __setattr__(app, key, value):
        return object.__setattr__(BlazeioMultiplexerConf.conf, key, value)

Protocols = _Protocols()

if __name__ == "__main__": ...