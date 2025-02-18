# Blazeio.Client
from ..Dependencies import *
from ..Modules.request import *
from collections.abc import Iterable

from ssl import create_default_context, SSLError, Purpose

class Utl:
    @classmethod
    async def split_before(app, str_: (bytearray, bytes, str), to_find: (bytearray, bytes, str)):
        if (idx := str_.find(to_find)) != -1:
            return str_[:idx]
        else:
            return False

    @classmethod
    async def split_between(app, str_: (bytearray, bytes, str), to_find: (bytearray, bytes, str)):
        if (idx := str_.find(to_find)) != -1:
            return (str_[:idx], str_[idx + len(to_find):])
        else:
            return False

    @classmethod
    async def split_after(app, str_: (bytearray, bytes, str), to_find: (bytearray, bytes, str)):
        if (idx := str_.find(to_find)) != -1:
            return str_[idx + len(to_find):]
        else:
            return False

class BlazeioClientProtocol(BufferedProtocol):
    __slots__ = (
        '__is_at_eof__',
        '__is_alive__',
        'transport',
        '__buff__',
        '__stream__',
        '__buff_requested__',
        '__buff__memory__',
        '__stream__sleep',
        '__chunk_size__',
    )

    def __init__(app, **kwargs):
        app.__chunk_size__ = 1024
        app.__is_at_eof__ = False
        app.__buff_requested__ = False
        app.__stream__sleep = 0
        
        if kwargs:
            for key, val in kwargs.items():
                if key in app.__slots__:
                    setattr(app, key, val)

        app.__stream__ = deque()
        app.__buff__ = bytearray(app.__chunk_size__)
        app.__buff__memory__ = memoryview(app.__buff__)

    async def set_buffer(app, sizehint: int):
        app.__buff__ = bytearray(sizehint)

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.__is_alive__ = True

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc):
        app.__is_alive__ = False

    def buffer_updated(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(nbytes)

    async def ensure_reading(app):
        if not app.transport.is_reading() and not app.__stream__:
            app.transport.resume_reading()

    async def pull(app):
        while True:
            await app.ensure_reading()

            while app.__stream__:
                if isinstance(chunk := app.__stream__.popleft(), int):
                    chunk = bytearray(app.__buff__memory__[:chunk])

                yield chunk

                await app.ensure_reading()

            if not app.__stream__:
                if app.transport.is_closing() or app.__is_at_eof__: break

            await sleep(app.__stream__sleep)

            if not app.__stream__: yield None

    def get_buffer_old(app, sizehint):
        try:
            if sizehint >= len(app.__buff__):
                app.__buff__ = bytearray(sizehint)
                return app.__buff__memory__[:sizehint]
            else:
                return app.__buff__memory__[:len(app.__buff__)]

        except Exception as e:
            print("get_buffer Exception: %s" % str(e))

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
        elif sizehint <= 0:
            sizehint = len(app.__buff__memory__)

        return app.__buff__memory__[:sizehint]

    async def push(app, data: (bytes, bytearray)):
        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

    async def ayield(app, timeout: float = 60.0):
        idle_time = None

        async for chunk in app.pull():
            yield chunk

            if chunk is not None:
                if idle_time is not None:
                    idle_time = None
            else:
                if idle_time is None:
                    idle_time = perf_counter()
                
                if perf_counter() - idle_time > timeout:
                    break

ssl_context = create_default_context()

class Session:
    __slots__ = ("transport", "protocol", "args", "kwargs", "host", "port", "path", "headers", "buff", "method", "content_length", "received_len", "response_headers", "status_code", "proxy", "connect_only", "timeout")

    def __init__(app, *args, **kwargs):
        app.args, app.kwargs = args, kwargs
        app.response_headers = defaultdict(str)
        app.status_code = 0

    async def __aenter__(app):
        return await app.create_connection(*app.args, **app.kwargs)

    async def __aexit__(app, exc_type, exc_value, traceback):
        app.protocol.transport.close()

        if exc_type:
            raise exc_type(exc_value)

        return

    async def url_to_host(app, url: str, scheme_sepr: str = "://", host_sepr: str = "/", param_sepr: str = "?", port_sepr: str = ":"):
        parsed_url = {}

        if (idx := url.find(scheme_sepr)) != -1:
            parsed_url["hostname"] = url[idx + len(scheme_sepr):]

            if (idx := parsed_url["hostname"].find(host_sepr)) != -1:
                parsed_url["path"], parsed_url["hostname"] = parsed_url["hostname"][idx:], parsed_url["hostname"][:idx]

            if (idx := parsed_url["hostname"].find(port_sepr)) != -1:
                parsed_url["port"], parsed_url["hostname"] = int(parsed_url["hostname"][idx + len(port_sepr):]), parsed_url["hostname"][:idx]

            if (idx := parsed_url["path"].find(param_sepr)) != -1:
                parsed_url["query"], parsed_url["path"] = parsed_url["path"][idx + len(param_sepr):], parsed_url["path"][:idx]

        host = parsed_url.get("hostname")
        path = parsed_url.get("path")
        port = parsed_url.get("port")
        
        if (query := parsed_url.get("query")):
            params = await Request.get_params(url="?%s" % query)
            query = "?"
    
            for k,v in params.items():
                v = await Request.url_encode(v)
    
                if query == "?": x = ""
                else: x = "&"
    
                query += "%s%s=%s" % (x, k, v)
    
            path += query

        if not port:
            if url.startswith("https"):
                port = 443
            else:
                port = 80
        
        # await p("%s--%s--%s--\n%s" % (host, port, path, url))

        return host, port, path

    async def create_connection(app, url: str = "", method: str = "", headers: dict = {}, connect_only: bool = False, host = 0, port: int = 0, path: str = "", content = None, proxy={}, add_host=True, timeout=10.0, **kwargs):
        app.method = method
        app.headers = dict(headers)
        app.proxy = dict(proxy)
        app.connect_only = connect_only
        app.timeout = timeout

        if not host and not port:
            app.host, app.port, app.path = await app.url_to_host(url)
        else:
            app.host, app.port, app.path, app.connect_only = host, port, path, connect_only

        if not app.connect_only:
            app.transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**kwargs),
                host=app.host,
                port=app.port,
                ssl=ssl_context if app.port == 443 else None,
            )
        else:
            app.transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**kwargs),
                host=app.host,
                port=app.port,
                **{a:b for a,b in kwargs.items() if a not in BlazeioClientProtocol.__slots__ and a not in app.__slots__}
            )

        if app.connect_only: return app

        if content is not None and not app.headers.get("Content-Length") and app.method not in {"GET", "HEAD", "OPTIONS"}:
            if not isinstance(content, (bytes, bytearray)):
                app.headers["Transfer-Encoding"] = "chunked"
            else:
                app.headers["Content-Length"] = str(len(content))

        if add_host:
            if not all(h in app.headers for h in ["Host", "authority", ":authority", "X-Forwarded-Host"]): app.headers["Host"] = app.host

        http_version = "1.1"

        payload = bytearray("%s %s HTTP/%s\r\n" % (app.method, app.path, http_version), "utf-8")

        for key, val in app.headers.items(): payload.extend(b"%s: %s\r\n" % (key.encode(), val.encode()))

        payload.extend(b"\r\n")

        await app.protocol.push(payload)

        if content is not None:
            if app.headers.get("Content-Length"):
                async for chunk in content: await app.protocol.push(chunk)

            elif app.headers.get("Transfer-Encoding") == "chunked":
                async for chunk in content:
                    chunk = b"%X\r\n%s\r\n" % (len(chunk), chunk)

                    await app.protocol.push(chunk)
                    
                await app.protocol.push(b"0\r\n\r\n")

            await app.prepare_http()

        return app

    async def prepare_http(app, sepr1=b"\r\n", sepr2=b": ", header_end = b"\r\n\r\n", headers=None,):
        if app.response_headers: return

        buff = bytearray()
        async for chunk in app.protocol.ayield():
            if not chunk: continue
            buff.extend(chunk)

            if (idx := buff.find(header_end)) != -1:
                headers, buff = buff[:idx], buff[idx + len(header_end):]
                app.protocol.__stream__.appendleft(buff)
                break

        while headers and (idx := headers.find(sepr1)):
            await sleep(0)

            if idx != -1: header, headers = headers[:idx], headers[idx + len(sepr1):]
            else: header, headers = headers, bytearray()

            if (idx := header.find(sepr2)) == -1:
                if not app.status_code:
                    app.status_code = header[header.find(b" "):].decode("utf-8").strip()
                    app.status_code = int(app.status_code[:app.status_code.find(" ")].strip())

                continue
            
            key, value = header[:idx], header[idx + len(sepr2):]
            
            app.response_headers[key.decode("utf-8").lower()] = value.decode("utf-8")
        
        app.response_headers = dict(app.response_headers)
        app.received_len, app.content_length = 0, int(app.response_headers.get('content-length',  0))

    async def get_handler(app):
        if app.response_headers.get("transfer-encoding"):
            handler = app.handle_chunked
        elif app.response_headers.get("content-length"):
            handler = app.handle_raw
        else:
            handler = app.protocol.pull

        return handler

    async def handle_chunked(app, endsig =  b"0\r\n\r\n", sepr1=b"\r\n",):
        end, buff = False, bytearray()
        read, size = 0, False

        async for chunk in app.protocol.ayield():
            if chunk:
                if endsig in chunk or endsig in chunk: end = True

            if not chunk: continue
            if not size:
                buff.extend(chunk)
                try:
                    if (idx := buff.find(sepr1)) != -1:
                        if buff[:idx] != b'':
                            size, buff = int(buff[:idx], 16), buff[idx + len(sepr1):]
                        else:
                            buff = buff[idx + len(sepr1):]
                            if (idx := buff.find(sepr1)):
                                size, buff = int(buff[:idx], 16), buff[idx + len(sepr1):]
                            else:
                                continue

                        chunk = buff
                    else:
                        continue

                except Exception as e:
                    await Log.critical(e)
                    continue

            read += len(chunk)

            if read < size:
                yield chunk
            else:
                excess_chunk_size = read - size
                chunk_size = len(chunk) - excess_chunk_size

                chunk, buff = chunk[:chunk_size], bytearray(chunk[chunk_size:])

                read, size = 0, False
                yield chunk

            if end: break

    async def handle_raw(app):
        async for chunk in app.protocol.ayield():
            if app.received_len >= app.content_length: break

            if not chunk: continue
            app.received_len += len(chunk)

            yield chunk

    async def pull(app, http=True):
        if http and not app.response_headers:
            await app.prepare_http()
        
        handler = await app.get_handler()

        async for chunk in handler():
            if chunk:
                yield chunk
    
    async def aread(app, decode=False):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)

        return data if not decode else data.decode("utf-8")
    
    async def json(app):
        return loads(await app.aread(decode=True))

    async def push(app, *args):
        return await app.protocol.push(*args)

if __name__ == "__main__":
    pass