from ..Dependencies import *
from ..Dependencies.alts import DictView, plog, memarray
from ..Modules.request import *
from ..Modules.streaming import *
from ..Modules.server_tools import *
from ..Modules.reasons import *

class Rutils(ContentDecoders):
    __slots__ = ()
    def __init__(app):
        ...

    def __getattr__(app, *_args):
        def method(*args, **kwargs):
            func = getattr(Request, *_args)
            
            if not "url_" in func.__name__:
                if args:
                    if not Context.is_prot(args[0]):
                        args = (Context._r(), *args)
                else:
                    args = (Context._r(),)

            return func(*args, **kwargs)

        return method

    def r(app):
        return Context._r()

    def multipart(app, *args):
        return Multipartdemux(*args)

    @classmethod
    async def aread(cls, app = None, decode=False):
        if not app: app = Context._r()
        if app.content_length: return await cls.read_exactly(app, app.content_length, decode)

        data = bytearray()
        async for chunk in app.pull(): data.extend(chunk)
        
        if (encoding := app.headers.get("Content-encoding", None)) and (decoder := getattr(app, "%s_decoder" % encoding, None)):
            data = await decoder(bytes(data))

        return data if not decode else data.decode()
    
    @classmethod
    async def read_exactly(cls, app = None, size: int = 0, decode=False):
        if not app: app = Context._r()
        data, point = memarray(size), 0
        async for chunk in app.pull():
            len_ = len(chunk)
            rem = (size-point)

            if len_ > rem:
                chunk = chunk[:rem]
                len_ = len(chunk)

            data[point: point + len_] = chunk

            point += len_
            if point >= size: break

        return data if not decode else data.decode()
    
    @classmethod
    async def text(cls, app = None):
        if not app: app = Context._r()
        return await cls.aread(app, True)

    @classmethod
    async def json(cls, app = None):
        if not app: app = Context._r()
        return Dot_Dict(loads(await cls.aread(app, True)))
    
    @classmethod
    def clear_protocol(cls, app = None):
        if not app: app = Context._r()
        app.__init__(app.on_client_connected, app.__evt__.loop, len(app.__buff__))

class ExtraToolset:
    __slots__ = ()
    prepare_http_sepr1 = b"\r\n"
    prepare_http_sepr2 = b": "
    prepare_http_header_end = b"\r\n\r\n"
    handle_chunked_endsig =  b"0\r\n\r\n"
    handle_chunked_sepr1 = b"\r\n"
    utils = Rutils()

    def headers_to_http_bytes(app, headers):
        payload = b""
        for key in headers:
            if isinstance(val := headers[key], list):
                for hval in val:
                    payload += b"%s: %s%s" % (str(key).encode(), str(hval).encode(), app.prepare_http_sepr1)
                continue
    
            payload += b"%s: %s%s" % (str(key).encode(), str(val).encode(), app.prepare_http_sepr1)
    
        return payload + app.prepare_http_sepr1
    
    def __iadd__(app, data: (bytes, bytearray)):
        if not app.__prepared_headers__:
            app.__prepared_headers__ = bytearray(b"")
        return app.__prepared_headers__.extend(data)

    def __getattr__(app, *_args):
        def method(*args, **kwargs):
            func = getattr(app.utils, *_args)

            if (not args) or (args[0] is app):
                args = (app, *args)
            
            return func(*args, **kwargs)

        return method

    async def write_raw(app, data: (bytes, bytearray)):
        if app.encoder: data = await app.encoder(data)

        return await app.writer(data)

    async def write_chunked(app, data):
        if app.encoder: data = await app.encoder(data)

        if isinstance(data, (bytes, bytearray)):
            await app.writer(b"%X\r\n%s\r\n" % (len(data), data))
        elif isinstance(data, (str, int)):
            raise Err("Only (bytes, bytearray, Iterable) are accepted")
        else:
            async for chunk in data:
                await app.writer(b"%X\r\n%s\r\n" % (len(chunk), chunk))

            await app.write_chunked_eof()

    async def write_event_stream(app, data, start: bytes = b"data: ", end: bytes = b"\n\n"):
        if app.encoder: data = await app.encoder(data)

        if isinstance(data, (dict, list)):
            data = dumps(data, indent=0).encode()

        if data[:len(start)] != start:
            data = b"%b%b%b" % (start, data, end)

        return await app.writer(data)

    async def write_chunked_eof(app, data: (tuple[bool, AsyncIterable[bytes | bytearray]] | None) = None):
        if data:
            await app.write(data)

        await app.writer(app.handle_chunked_endsig)
    
    async def eof(app, *args):
        if app.write == app.write_chunked:
            method = app.write_chunked_eof
        else:
            if args and args[0]:
                method = app.write_raw
            else:
                method = None

        if method is not None: await method(*args)

    async def handle_chunked(app, *args, **kwargs):
        if app.headers is None: await app.reprepare()
        end, buff = False, memarray()
        read, size, idx = 0, False, -1

        async for chunk in app.request():
            if size == False:
                buff.extend(chunk)
                if (idx := buff.find(app.handle_chunked_sepr1)) == -1: continue

                if not (s := buff[:idx]): continue

                size, buff = int(s, 16), memarray(buff[idx + len(app.handle_chunked_sepr1):])

                if size == 0: end = True

                if len(buff) >= size:
                    chunk, buff = buff, memarray(buff[len(buff):])
                else:
                    chunk, buff = buff[:size], memarray(buff[len(buff):])

            read += len(chunk)

            if read > size:
                chunk_size = len(chunk) - (read - size)

                chunk, __buff__ = chunk[:chunk_size], memarray(chunk[chunk_size + 2:])

                app.prepend(__buff__)

                read, size = 0, False
            
            yield chunk

            if end: break

    async def set_cookie(app, name: str, value: str, expires: str = "Tue, 07 Jan 2030 01:48:07 GMT", secure = True, http_only = False):
        if secure: secure = "Secure; "
        else: secure = ""

        if http_only: http_only = "HttpOnly; "
        else: http_only = ""

        app.__prepared_headers__ += bytearray("Set-Cookie: %s=%s; Expires=%s; %s%sPath=/\r\n" % (name, value, expires, http_only, secure), "utf-8")

    async def handle_raw(app, *args, **kwargs):
        if app.headers is None: await app.reprepare()

        if app.method in app.non_bodied_methods or app.current_length >= app.content_length: return

        async for chunk in app.request():
            if chunk:
                app.current_length += len(chunk)
                yield chunk

            if app.current_length >= app.content_length: break

    async def prepare(app, headers: dict = {}, status: int = 200, reason: str = "", encode_resp: bool = True, encode_event_stream: bool = True):
        payload = ('HTTP/1.1 %d %s\r\n' % (status, StatusReason.reasons.get(status, "Unknown"))).encode()

        if app.__prepared_headers__:
            payload += app.__prepared_headers__
            app.__prepared_headers__.clear()

        await app.writer(payload)
        
        headers_view = DictView(headers)

        app.__is_prepared__ = True
        app.__status__ = status

        if (val := headers_view.get(key := "Server")):
            headers[str(headers_view._capitalized.get(key))] = ["Blazeio", val]
        else:
            headers[key] = "Blazeio"

        if (val := headers_view.get("Content-encoding")) and encode_resp:
            app.encoder = getattr(app, val, None)
        else:
            app.encoder = None

        if headers_view.get("Transfer-encoding") == "chunked":
            app.write = app.write_chunked
        elif headers_view.get("Content-length"):
            app.write = app.write_raw
        elif headers_view.get("Content-type") == "text/event-stream" and encode_event_stream:
            app.write = app.write_event_stream
        else:
            app.write = app.write_raw

        await app.writer(app.headers_to_http_bytes(headers))

    def br(app, data: (bytes, bytearray)):
        return to_thread(brotlicffi_compress, bytes(data))

    async def gzip(app, data: (bytes, bytearray)):
        encoder = compressobj(wbits=31)
        data = encoder.compress(bytes(data))
        if (_ := encoder.flush()): data += _
        return data

    async def reprepare(app):
        await Request.prepare_http_request(app)

if __name__ == "__main__":
    pass