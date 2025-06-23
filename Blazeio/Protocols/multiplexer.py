import Blazeio as io
import socket

class BlazeioMultiplexer:
    __slots__ = ("__streams__", "__updater__", "__busy_write__", "__received_size", "__expected_size", "__current_stream_id", "__current_stream", "protocol", "__buff", "__prepends__")
    _data_bounds_ = (b"<::", b"::>", b"<::>", b"<::__close_stream__::>", b"")

    def __init__(app, protocol):
        app.protocol = protocol
        app.__streams__ = {}
        app.__current_stream = None
        app.__buff = bytearray()
        app.__busy_write__ = io.ioCondition(evloop = io.loop)
        app.__updater__ = io.loop.create_task(app.update_streams())
        app.__prepends__ = io.deque()

    def choose_stream(app):
        return app.__prepends__ or app.protocol.__stream__

    async def ensure_reading(app):
        if not app.choose_stream():
            await app.protocol.ensure_reading()

    async def pull(app):
        while True:
            await app.ensure_reading()
            while (stream := app.choose_stream()):
                yield stream.popleft()
            else:
                if app.protocol.transport.is_closing() or app.protocol.__is_at_eof__: break

    def clear_state(app):
        app.__received_size, app.__expected_size, app.__current_stream_id = 0, NotImplemented, NotImplemented
    
    def _parse_bounds(app):
        if (idx := app.__buff.find(app._data_bounds_[0])) == -1 or (idb := app.__buff.find(app._data_bounds_[1])) == -1: return
        return (idx, idb)

    def _set_stream(app):
        if not (ranges := app._parse_bounds()): return
        else: idx, idb = ranges

        if app.__current_stream_id is NotImplemented:
            app.__current_stream_id, app.__buff = bytes(memoryview(app.__buff)[:idb + len(app._data_bounds_[1])]), app.__buff[idb + len(app._data_bounds_[1]):]

        return True
    
    def _eof_check(app, chunk):
        if app.__expected_size == len(app._data_bounds_[2]) and bytes(memoryview(chunk)[:app.__expected_size]) == app._data_bounds_[2]:
            chunk = bytes(memoryview(chunk)[app.__expected_size:])
            app.__expected_size -= len(app._data_bounds_[2])
            app.__current_stream.eof_received = True
            app.__current_stream.__on_eof_received__.set()
            return chunk
        
        return None

    async def _stream_closure_check(app, chunk):
        if app.__expected_size == len(app._data_bounds_[3]) and bytes(memoryview(chunk)[:app.__expected_size]) == app._data_bounds_[3]:
            chunk = bytes(memoryview(chunk)[app.__expected_size:])
            app.__expected_size -= len(app._data_bounds_[3])
            await app.protocol.stream_closed(app.__current_stream)
            return chunk

        return None

    async def update_streams(app):
        app.clear_state()
        async for chunk in app.pull():
            if app.__expected_size is NotImplemented:
                app.__buff.extend(chunk)
                if not app._set_stream(): continue

                if not (ranges := app._parse_bounds()): continue
                else: idx, idb = ranges

                app.__expected_size, app.__buff = int(bytes(memoryview(app.__buff)[idx + len(app._data_bounds_[0]):idb]), 16), app.__buff[idb + len(app._data_bounds_[1]):]

                chunk, _ = bytes(memoryview(app.__buff)[:]), app.__buff.clear()

                if not (stream := app.__streams__.get(app.__current_stream_id)):
                    stream = app.protocol.accept(app.__current_stream_id)

                app.__current_stream = stream

                if (_ := app._eof_check(chunk)) is not None:
                    chunk = _
                elif (_ := await app._stream_closure_check(chunk)) is not None:
                    chunk = _
                else:
                    app.__current_stream.expected_size += app.__expected_size

            app.__received_size += len(chunk)

            if app.__received_size >= app.__expected_size:
                if app.__received_size > app.__expected_size:
                    chunk_size = (len(chunk) - (app.__received_size - app.__expected_size))
                    remainder, chunk = bytes(memoryview(chunk)[chunk_size:]), bytes(memoryview(chunk[:chunk_size]))
                    app.__prepends__.appendleft(remainder)

                app.clear_state()

            app.__current_stream.received_size += len(chunk)
            app.__current_stream.__stream__.append(chunk)
            app.__current_stream.__evt__.set()

    def stream_id_gen(app):
        return b"%b{stream_%X}%b" % (app._data_bounds_[0], len(app.__streams__), app._data_bounds_[1])

    def enter_stream(app, _id: (None, bytes) = None, instance = None):
        if not _id:
            _id = app.stream_id_gen()

        if not instance:
            instance = Stream

        app.__streams__[_id] = (stream := instance(_id, app))
        return stream

    def metadata(app, _id: (bytes, bytearray), _len: int):
        return b"%b%b%X%b" % (_id, app._data_bounds_[0], _len, app._data_bounds_[1])

    def state(app):
        return {key: str(getattr(app, key, "")) for key in app.__slots__}

class Stream:
    __slots__ = ("protocol", "id", "id_str", "__stream__", "__evt__", "expected_size", "received_size", "eof_received", "_used", "eof_sent", "_close_on_eof", "__prepends__", "transport", "pull", "writer", "chunk_size", "__on_exit__", "__on_eof_received__", "__stream_closed__", "__wait_closed__", "sent_size")

    def __init__(app, _id, protocol):
        app.protocol = protocol
        app.transport = app.protocol.protocol.transport
        app.id = _id
        app.id_str = app.id.decode()
        app.chunk_size = app.calc_chunk_size()
        app.__stream_closed__ = False
        app.pull = app.__pull__
        app.writer = app.__writer__
        app.__stream__ = io.deque()
        app.__prepends__ = io.deque()

        app.__evt__ = io.SharpEvent(False, evloop = io.loop)
        app.__on_eof_received__ = io.SharpEvent(False, evloop = io.loop)
        app.__wait_closed__ = io.SharpEvent(False, evloop = io.loop)

        app.clear_state()

    def calc_chunk_size(app, _min: int = 256):
        chunk_size = int(len(app.protocol.protocol.__buff__) / 6)
        if chunk_size < _min: chunk_size = _min
        return chunk_size

    def keep_alive(app):
        app._close_on_eof = False

    def clear_state(app):
        app.received_size, app.sent_size, app.expected_size, app.eof_received, app._used, app.eof_sent, app._close_on_eof = 0, 0, 0, False, False, False, True

    def state(app):
        return {key: str(getattr(app, key, "")) for key in Stream.__slots__}

    def choose_stream(app):
        return app.__prepends__ or app.__stream__

    def prepend(app, data):
        app.__prepends__.appendleft(data)
        app.__evt__.set()

    async def __aenter__(app):
        if app._used:
            app.clear_state()
        return app

    async def __aexit__(app, exc_t, exc_v, tb):
        if app._used and not app.eof_sent:
            await app.__eof__()

        return False

    async def __eof__(app, data: (None, bytes, bytearray) = None, close: bool = False):
        if data:
            await app.__writer__(data)

        if app.eof_sent: return
        app.eof_sent, app._close_on_eof = True, close
        return await app.__writer__(app.protocol._data_bounds_[2], False)

    async def ensure_reading(app):
        if not app.choose_stream():
            if not app.__stream_closed__:
                await app.__evt__.wait()
                app.__evt__.clear()

    async def __pull__(app):
        while True:
            await app.ensure_reading()
            while (__stream__ := app.choose_stream()):
                if not (chunk := __stream__.popleft()):
                    if app.eof_received:
                        return

                yield chunk
            else:
                if app.__stream_closed__:
                    await app.__close__()
                    return

    async def __to_chunks__(app, data: memoryview):
        while len(data) > app.chunk_size:
            chunk, data = data[:app.chunk_size], data[app.chunk_size:]
            yield chunk

        yield data

    async def __writer__(app, data: (bytes, bytearray), add: bool = True):
        if not app._used: app._used = True

        if not app.transport.is_closing() and not app.__stream_closed__:
            data_size = len(data)

            async for chunk in app.__to_chunks__(memoryview(data)):
                if (chunk_size := len(chunk)) != data_size:
                    chunk = bytes(chunk)
                else:
                    chunk = data

                async with app.protocol.__busy_write__:
                    await app.protocol.protocol.buffer_overflow_manager()
                    app.transport.write(app.protocol.metadata(app.id, chunk_size) + chunk)

            if add: app.sent_size += data_size
        else:
            raise app.protocol.protocol.__stream_closed_exception__()

    async def read_data(app, decode: bool = False):
        app.keep_alive()
        _ = bytearray()
        async for chunk in app.pull():
            _.extend(chunk)

        return _.decode() if decode else _

    async def __close__(app):
        if not app.__stream_closed__:
            await app.__writer__(app.protocol._data_bounds_[3], False)
        
        await app.protocol.protocol.stream_closed(app)
        await app.__wait_closed__.wait()

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

class Stream_Client(Stream):
    def __init__(app, *args):
        Stream.__init__(app, *args)
        app.__timeout__ = None
        app.cancel_on_disconnect = True
        app.push, app.write = app.writer, app.writer

class BlazeioClientProtocol(io.BlazeioClientProtocol):
    __slots__ = ("multiplexer")
    __stream_closed_exception__ = io.ServerDisconnected

    def __getattr__(app, name):
        return getattr(app.multiplexer, name)

    def connection_made(app, transport):
        super().connection_made(transport)
        app.multiplexer = BlazeioMultiplexer(app)

    def accept(app, _id: (None, bytes) = None):
        return app.multiplexer.enter_stream(_id, Stream_Client)

    async def stream_closed(app, stream):
        app.multiplexer.__streams__.pop(stream.id, None)
        stream.__stream_closed__ = True
        stream.__wait_closed__.set()

class BlazeioServerProtocol(io.BlazeioServerProtocol):
    __slots__ = ("multiplexer", "tasks", "socket", "transport")
    __stream_closed_exception__ = io.ClientDisconnected

    def connection_made(app, transport):
        app.transport = transport
        app.transport.pause_reading()
        app.tasks = []
        app.multiplexer = BlazeioMultiplexer(app)
        app.socket = transport.get_extra_info('socket')

    def accept(app, _id):
        app.tasks.append(task := io.loop.create_task(app.__transporter__(r := app.multiplexer.enter_stream(_id, Stream_Server))))

        task.__BlazeioServerProtocol__ = r
        return r

    async def stream_closed(app, stream):
        app.multiplexer.__streams__.pop(stream.id, None)
        stream.__stream_closed__ = True
        stream.__wait_closed__.set()

    async def __transporter__(app, r):
        try:
            await app.on_client_connected(r)
        finally:
            await r.__eof__()
            await r.__close__()

    def cancel(app):
        for task in app.tasks: task.cancel()
        app.close()

if __name__ == "__main__":
    pass
