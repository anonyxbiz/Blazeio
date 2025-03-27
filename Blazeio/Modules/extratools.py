from ..Dependencies import *
from .request import *
from .streaming import *
from .server_tools import *
from .reasons import *

class ExtraToolset:
    __slots__ = ()
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
        await app.writer(b"0\r\n\r\n")
    
    async def eof(app):
        if app.write == app.write_chunked:
            return await app.write_chunked_eof()

    async def handle_chunked(app, endsig =  b"0\r\n\r\n", sepr1=b"\r\n",):
        end, buff = False, bytearray()
        read, size, idx = 0, False, -1

        async for chunk in app.ayield():
            if not chunk: chunk = b""
            
            if endsig in buff or endsig in chunk: end = True

            if size == False:
                buff.extend(chunk)
                if (idx := buff.find(sepr1)) == -1: continue

                if not (s := buff[:idx]):
                    buff = buff[len(sepr1):]
                    if (ido := buff.find(sepr1)) != -1:
                        s = buff[:ido]
                        idx = ido
                    else:
                        if not end: continue

                size, buff = int(s, 16), buff[idx + len(sepr1):]

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

    async def handle_raw(app, *args):
        if app.headers is None: raise Err("Request not prepared.")

        if app.method in app.non_bodied_methods or app.current_length >= app.content_length: return

        async for chunk in app.ayield(*args):
            if chunk:
                app.current_length += len(chunk)
                yield chunk

            if app.current_length >= app.content_length: break

    async def prepare(app, headers: dict = {}, status: int = 206, reason: (str, bool) = None, protocol: str = "HTTP/1.1"):
        if headers: headers = {key.capitalize(): val for key, val in headers.items()}
        if headers.get("Transfer-encoding"): app.write = app.write_chunked
        else: app.write = app.write_raw

        if not app.__is_prepared__:
            if not reason:
                reason = StatusReason.reasons.get(status, "Unknown")

            await app.writer(b"%s %s %s\r\nServer: Blazeio\r\n" % (protocol.encode(), str(status).encode(), reason.encode()))

            if app.__cookie__:
                await app.writer(app.__cookie__)

            app.__is_prepared__ = True
            app.__status__ = status

        if headers:
            if (encoding := headers.get("Content-encoding")):
                app.encoder = getattr(app, encoding, None)

            for key, val in headers.items():
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

if __name__ == "__main__":
    pass