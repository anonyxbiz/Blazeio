from ..Dependencies import *
from .request import *
from .streaming import *
from .server_tools import *
from .reasons import *
from ..Client import Async

class ExtraToolset:
    __slots__ = ()
    prepare_http_sepr1 = b"\r\n"
    prepare_http_sepr2 = b": "
    prepare_http_header_end = b"\r\n\r\n"
    handle_chunked_endsig =  b"0\r\n\r\n"
    handle_chunked_sepr1 = b"\r\n"

    def __init__(app):
        pass

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
            method = None

        if method is not None: await method(*args)

    async def handle_chunked(app, *args, **kwargs):
        if app.headers is None: await app.reprepare()
        end, buff = False, bytearray()
        read, size, idx = 0, False, -1

        async for chunk in app.ayield(*args, **kwargs):
            if size == False:
                buff.extend(chunk)
                if (idx := buff.find(app.handle_chunked_sepr1)) == -1: continue

                if not (s := buff[:idx]): continue

                size, buff = int(s, 16), buff[idx + len(app.handle_chunked_sepr1):]

                if size == 0: end = True

                if len(buff) >= size:
                    chunk, buff = buff, bytearray()
                else:
                    chunk, buff = buff[:size], bytearray()

            read += len(chunk)

            if read <= size:
                pass
            else:
                excess_chunk_size = read - size
                chunk_size = len(chunk) - excess_chunk_size

                chunk, __buff__ = chunk[:chunk_size], bytearray(chunk[chunk_size + 2:])
                
                await app.prepend(__buff__)

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

        async for chunk in app.ayield(*args, **kwargs):
            if chunk:
                app.current_length += len(chunk)
                yield chunk

            if app.current_length >= app.content_length: break

    async def prepare(app, headers: dict = {}, status: int = 200, reason: str = "", encode_resp: bool = True):
        await app.writer(b'HTTP/1.1 %s %s\r\nServer: Blazeio\r\n' % (str(status).encode(), StatusReason.reasons.get(status, "Unknown").encode()))

        if app.__cookie__: await app.writer(app.__cookie__)

        app.__is_prepared__ = True
        app.__status__ = status

        for key, val in headers.items():
            if not hasattr(app, "encoder"):
                if key.capitalize() == "Content-encoding" and encode_resp:
                    app.encoder = getattr(app, val, None)

            if not hasattr(app, "write"):
                if key.capitalize() == "Transfer-encoding":
                    app.write = app.write_chunked

                elif key.capitalize() == "Content-length":
                    app.write = app.write_raw

            if isinstance(val, list):
                for hval in val: await app.writer(b"%s: %s\r\n" % (str(key).encode(), str(hval).encode()))
                continue

            await app.writer(b"%s: %s\r\n" % (str(key).encode(), str(val).encode()))

        await app.writer(b"\r\n")

        if not hasattr(app, "write"): app.write = app.write_raw
        if not hasattr(app, "encoder"): app.encoder = None

    async def write_raw(app, data: (bytes, bytearray)):
        if app.encoder: data = await app.encoder(data)

        return await app.writer(data)

    async def br(app, data: (bytes, bytearray)):
        return await to_thread(brotlicffi_compress, bytes(data))

    async def gzip(app, data: (bytes, bytearray)):
        encoder = compressobj(wbits=31)
        data = encoder.compress(bytes(data))
        if (_ := encoder.flush()): data += _
        return data
    
    async def reprepare(app):
        await Request.prepare_http_request(app)

if __name__ == "__main__":
    pass