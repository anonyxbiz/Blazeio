# Blazeio.Client
from ..Dependencies import *

from ssl import create_default_context, SSLError

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

class BlazeioClientProtocol(asyncProtocol):
    __slots__ = (
        '__stream__',
        '__is_at_eof__',
        '__is_alive__',
        'transport',
        '__max_buff_len__',
        'host',
        'port'
    )

    def __init__(app):
        app.__stream__ = deque()
        app.__is_at_eof__ = False
        app.__max_buff_len__ = 5

    def connection_made(app, transport):
        app.transport = transport
        app.__is_alive__ = True

    def data_received(app, data):
        app.__stream__.append(data)
        if len(app.__stream__) >= app.__max_buff_len__:
            app.transport.pause_reading()

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc):
        app.__is_alive__ = False

    async def pull(app):
        while True:
            while app.__stream__:
                if app.transport.is_reading(): app.transport.pause_reading()

                yield app.__stream__.popleft()

            if not app.__stream__:
                if app.__is_at_eof__: break
                if not app.transport.is_reading(): app.transport.resume_reading()
                if app.transport.is_closing(): break
                else: yield None

            await sleep(0)

    async def push(app, data: (bytes, bytearray)):
        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

ssl_context = create_default_context()

class __Pool__:
    __slots__ = ()
    conns = {}

    def __init__(app): pass

    async def get_conn(app, host, port):
        if not (conn := app.conns.get((host, port))):
            conn = await loop.create_connection(
                lambda: BlazeioClientProtocol(),
                host=host, port=port, ssl=ssl_context if port == 443 else None
            )
            app.conns[(host, port)] = conn

        return conn

# Pool = __Pool__()

class Session:
    __slots__ = ("transport", "protocol", "args", "kwargs", "host", "port", "path", "headers", "buff", "method", "content_length", "received_len", "response_headers", "status_code")

    def __init__(app, *args, **kwargs):
        app.args, app.kwargs = args, kwargs
        app.response_headers = defaultdict(str)
        app.status_code = 0

    async def url_to_host(app, url: str, sepr: str = "://", sepr2: str = ":", sepr3: str = "/"):
        host = url

        if "https" in url:
            port: int = 443
        else:
            port: int = 80

        if (_ := await Utl.split_after(host, sepr)):
            host = _
        else:
            raise Err("%s is not a valid host" % host)

        if (_ := await Utl.split_between(host, sepr3)):
            host = _[0]
            path = sepr3 + _[1]

            if (__ := await Utl.split_between(host, sepr2)):
                port = int(__[1])
                host = __[0]
        else:
            path = "/"

        return host, port, path
    
    async def __aenter__(app):
        return await app.create_connection(*app.args, **app.kwargs)

    async def __aexit__(app, ext1, ext2, ext3):
        return
        try:
            pass
        except CancelledError: pass
        except Exception as e:
            await p("Err: %s" % str(e))

    async def create_connection(app, url: str = "", method: str = "", headers: dict = {}, connect_only: bool = False, host: int = 0, port: int = 0, path: str = "", content = None):
        if not host and not port and not path:
            app.method = method
            app.host, app.port, app.path = await app.url_to_host(url)

            app.headers = dict(headers)
            if not "Host" in app.headers: app.headers["Host"] = app.host
        else:
            app.host, app.port, app.path, connect_only = host, port, path, True

        # app.transport, app.protocol = await Pool.get_conn(app.host, app.port)

        app.transport, app.protocol = await loop.create_connection(
            lambda: BlazeioClientProtocol(),
            host=app.host, port=app.port, ssl=ssl_context if app.port == 443 else None
        )

        if connect_only:
            return app.protocol
        
        if content is not None and not app.headers.get("Content-Length"):
            app.headers["Transfer-Encoding"] = "chunked"

        await app.protocol.push(bytearray("%s %s HTTP/1.1\r\n" % (app.method, app.path), "utf-8"))

        for key, val in app.headers.items(): await app.protocol.push(bytearray("%s: %s\r\n" % (key, val), "utf-8"))

        await app.protocol.push(b"\r\n")
        
        if content is not None:
            async for chunk in content:
                chunk = b"%X\r\n%s\r\n" % (len(chunk), chunk)

                await app.protocol.push(chunk)
            
            await app.protocol.push(b"0\r\n\r\n")

            await app.prepare_http()

        return app
    
    async def push(app, *args): await app.protocol.push(*args)

    async def prepare_http(app, sepr1=b"\r\n", sepr2=b": ", header_end = b"\r\n\r\n", headers=None,):
        buff = bytearray()

        async for chunk in app.protocol.pull():
            if not chunk: continue
            buff.extend(chunk)
            if (idx := buff.find(header_end)) != -1:
                headers, buff = buff[:idx], buff[idx + len(header_end):]
                app.protocol.__stream__.appendleft(buff)
                break

        while headers and (idx := headers.find(sepr1)):
            if idx != -1: header, headers = headers[:idx], headers[idx + len(sepr1):]
            else: header, headers = headers, bytearray()

            if (idx := header.find(sepr2)) == -1:
                if not app.status_code:
                    app.status_code = header[header.find(b" "):].decode("utf-8").strip()
                    app.status_code = int(app.status_code[:app.status_code.find(" ")].strip())

                continue
            
            key, value = header[:idx], header[idx + len(sepr2):]
            
            app.response_headers[key.decode("utf-8")] = value.decode("utf-8")
        
        app.response_headers = dict(app.response_headers)
        app.received_len, app.content_length = 0, int(app.response_headers.get('Content-Length',  0))

    async def get_handler(app):
        if app.response_headers.get("Transfer-Encoding") == "chunked":
            handler = app.handle_chunked
        elif app.response_headers.get("Content-Length"):
            handler = app.handle_raw
        else:
            handler = app.protocol.pull

        return handler

    async def handle_chunked(app, endsig =  b"0\r\n\r\n", sepr1=b"\r\n",):
        buff, chunk_size = bytearray(), None

        async for chunk in app.protocol.pull():
            if not chunk: continue

            if not chunk_size:
                buff.extend(chunk)
                if (idx := buff.find(sepr1)) != -1:
                    chunk_size = b"" + buff[:idx]
                    chunk_size = int(chunk_size.decode(), 16)
                    chunk, buff = buff[idx + len(sepr1):], bytearray()
                else: continue
            

            if (endsig_idx := chunk.find(endsig)) != -1:
                chunk = chunk[:endsig_idx]
            
            if len(chunk) >= 10:
                if (sepr1_idx := chunk[:10].find(sepr1)) != -1:
                    chunk = chunk[sepr1_idx:]

            yield chunk

            if endsig_idx != -1: break

    async def handle_raw(app):
        async for chunk in app.protocol.pull():
            if not chunk and app.received_len >= app.content_length:
                break
            
            if not chunk: continue

            app.received_len += len(chunk)

            yield chunk
    
    async def pull(app, http=True):
        if http and not app.response_headers:
            await app.prepare_http()
        
        handler = await app.get_handler()

        async for chunk in handler():
            yield chunk
    
    async def aread(app, decode=False):
        data = bytearray()
        async for chunk in app.pull(): data.extend(chunk)

        return data if not decode else data.decode("utf-8")
    
    async def json(app):
        return loads(await app.aread(decode=True))
  
if __name__ == "__main__":
    pass