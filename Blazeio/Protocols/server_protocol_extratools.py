from ..Dependencies import *
from ..Dependencies.alts import DictView, plog, memarray
from ..Modules.request import *
from ..Modules.streaming import *
from ..Modules.server_tools import *
from ..Modules.reasons import *

class Multipartdemux:
    __slots__ = ("r", "headers", "buff", "boundary", "boundary_only", "header_bytes")
    boundary_eof = b"\r\n\r\n"
    boundary_eof_len = len(boundary_eof)
    boundary_start = b"----WebKitFormBoundary"
    header_start = b"\r\n"
    name_s = b"Content-Disposition: form-data; name="
    name_s = b";"

    def __init__(app, r = None):
        app.r = r
        app.header_bytes = None
        app.headers = ddict()
        app.buff = memarray()
        app.boundary = None

    async def __aexit__(app, exc_type, exc_value, tb):
        if exc_value: raise exc_value

    async def __aenter__(app):
        if not app.r:
            app.r = Context._r()
        app.r.pull = app.pull
        await app.prepare_multipart()
        return app
    
    async def prepare_multipart(app):
        idx, started = 0, 0
        async for chunk in app.r.request():
            app.buff.extend(chunk)
            if not started:
                if (idx := app.buff.find(app.boundary_start)) != -1 and (ide := app.buff.find(app.header_start)) != -1:
                    app.header_bytes, app.boundary, app.boundary_only, app.buff = app.buff[:ide], app.buff[idx:ide+len(app.header_start)], app.buff[idx:ide], memarray(app.buff[ide:])

                    started = 1
                else:
                    continue

            if (app.buff.endswith(app.boundary_eof)) or app.buff.count(app.boundary) >= app.buff.count(app.boundary_eof):
                break

        idx = app.buff.rfind(app.boundary)
        ide = app.buff[idx:].find(app.boundary_eof) + len(app.boundary_eof)

        app.header_bytes += app.buff[:idx+ide]
        app.buff = app.buff[idx + ide:]

        app.parse_header_bytes()
    
    def parse_header_bytes(app):
        header_bytes = app.header_bytes
        while (idx := header_bytes.find(app.boundary)) != -1:
            form_data = header_bytes[idx + len(app.boundary):]
            name = form_data[(idx := form_data.find(app.name_s) + len(app.name_s) + 6):]

            if (ide := name.find(app.boundary_eof)) != -1:
                form_data, name = name[ide + len(app.boundary_eof):], name[:ide]

            elif (ide := name.find(app.name_e)) != -1:
                form_data, name = name[ide + len(app.name_e):], name[:ide]

            value, form_data = form_data[:(idx := form_data.find(app.header_start))], form_data[idx + len(app.header_start):]
            
            app.headers[name[1:-1].decode()] = value.decode()

            header_bytes = form_data

    def is_eof(app, chunk):
        return bytes(memoryview(chunk)[len(chunk)-(len(app.boundary_only)+10):]).find(app.boundary_only) != -1

    def slice_trail(app, chunk):
        chunk_rem = bytes(memoryview(chunk)[:chunk.rfind(app.boundary_only)])

        return bytes(memoryview(chunk_rem)[:chunk_rem.find(app.header_start)])

    async def pull(app):
        if not app.headers:
            await app.prepare_multipart()

        if app.is_eof(app.buff):
            yield app.slice_trail(app.buff)
            return
        
        yield app.buff

        async for chunk in app.r.request():
            if app.is_eof(chunk):
                yield app.slice_trail(chunk)
                break

            yield chunk

class Rutils:
    __slots__ = ()
    def __init__(app):
        ...
    
    def __getattr__(app, *args):
        return getattr(Request, *args)

    def r(app):
        return Context._r()

    def multipart(app, *args):
        return Multipartdemux(*args)

    async def aread(app, decode=False):
        r = app.r()
        if r.content_length: return await app.read_exactly(r.content_length, decode)

        data = bytearray()
        async for chunk in r.pull(): data.extend(chunk)
        return data if not decode else data.decode()
    
    async def read_exactly(app, size: int, decode=False):
        r = app.r()
        data, point = memarray(size), 0
        async for chunk in r.pull():
            len_ = len(chunk)
            rem = (size-point)

            if len_ > rem:
                chunk = chunk[:rem]
                len_ = len(chunk)

            data[point: point + len_] = chunk

            point += len_
            if point >= size: break

        return data if not decode else data.decode()

    async def text(app):
        return await app.aread(True)

    async def json(app):
        return Dot_Dict(loads(await app.aread(True)))

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

        if not app.__cookie__: app.__cookie__ = bytearray(b"")

        app.__cookie__ += bytearray("Set-Cookie: %s=%s; Expires=%s; %s%sPath=/\r\n" % (name, value, expires, http_only, secure), "utf-8")

    async def handle_raw(app, *args, **kwargs):
        if app.headers is None: await app.reprepare()

        if app.method in app.non_bodied_methods or app.current_length >= app.content_length: return

        async for chunk in app.request():
            if chunk:
                app.current_length += len(chunk)
                yield chunk

            if app.current_length >= app.content_length: break

    async def prepare(app, headers: dict = {}, status: int = 200, reason: str = "", encode_resp: bool = True):
        payload = ('HTTP/1.1 %d %s\r\n' % (status, StatusReason.reasons.get(status, "Unknown"))).encode()

        if app.__cookie__: payload += app.__cookie__

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
        elif not hasattr(app, "write"):
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