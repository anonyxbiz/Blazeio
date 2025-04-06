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
        app.write = app.writer
        app.encoder = None

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

    async def write_chunked_eof(app):
        await app.writer(app.handle_chunked_endsig)
    
    async def eof(app):
        if app.write == app.write_chunked:
            return await app.write_chunked_eof()

    async def handle_chunked(app, *args, **kwargs):
        if app.headers is None: await app.reprepare()
        end, buff = False, bytearray()
        read, size, idx = 0, False, -1

        async for chunk in app.ayield(*args, **kwargs):
            if not chunk: chunk = b""

            if app.handle_chunked_endsig in buff or app.handle_chunked_endsig in chunk: end = True

            if size == False:
                buff.extend(chunk)
                if (idx := buff.find(app.handle_chunked_sepr1)) == -1: continue

                if not (s := buff[:idx]):
                    buff = buff[len(app.handle_chunked_sepr1):]
                    if (ido := buff.find(app.handle_chunked_sepr1)) != -1:
                        s = buff[:ido]
                        idx = ido
                    else:
                        if not end: continue

                size, buff = int(s, 16), buff[idx + len(app.handle_chunked_sepr1):]

                if size == 0: return

                if len(buff) >= size:
                    chunk = buff
                else:
                    chunk, buff = buff[:size], buff[size:]

            read += len(chunk)

            if read < size:
                yield chunk
            else:
                excess_chunk_size = read - size
                chunk_size = len(chunk) - excess_chunk_size

                chunk, buff = chunk[:chunk_size], bytearray(chunk[chunk_size:])

                read, size = 0, False
                yield chunk
            
            if end:
                if not buff: break

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

    async def prepare(app, headers: dict = {}, status: int = 206, reason: (str, bool) = None, protocol: str = "HTTP/1.1"):
        headers = {key.capitalize(): val async for key, val in Async.ite(headers)}

        if headers.get("Transfer-encoding"): app.write = app.write_chunked
        else: app.write = app.write_raw

        if not reason:
            reason = StatusReason.reasons.get(status, "Unknown")

        await app.writer(b"%s %s %s\r\nServer: Blazeio\r\n" % (protocol.encode(), str(status).encode(), reason.encode()))

        if app.__cookie__:
            await app.writer(app.__cookie__)

        app.__is_prepared__ = True
        app.__status__ = status
        
        if (encoding := headers.get("Content-encoding")):
            app.encoder = getattr(app, encoding, None)

        async for key, val in Async.ite(headers):
            if isinstance(val, list):
                for hval in val: await app.writer(b"%s: %s\r\n" % (key.encode(), hval.encode()))
                continue

            await app.writer(b"%s: %s\r\n" % (key.encode(), val.encode()))
        
        await app.writer(b"\r\n")

    async def write_raw(app, data: (bytes, bytearray)):
        if app.encoder: data = await app.encoder(data)

        return await app.writer(data)

    async def writer(app, data: (bytes, bytearray)):
        await app.buffer_overflow_manager()

        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")
    
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