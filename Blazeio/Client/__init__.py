# Blazeio.Client
from ..Dependencies import *
from urllib.parse import urlparse
from asyncio import BufferedProtocol
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

    def connection_made(app, transport):
        app.transport = transport
        app.__is_alive__ = True

    def data_received(app, data):
        app.__stream__.append(data)

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc):
        app.__is_alive__ = False

    async def pull(app):
        while True:
            while app.__stream__:
                app.transport.pause_reading()

                yield app.__stream__.popleft()

                app.transport.resume_reading()

            if not app.__stream__:
                if app.transport.is_closing(): raise Err("Client has disconnected.")

                if app.__is_at_eof__: raise Err("Client has disconnected.")

                if not app.transport.is_reading(): app.transport.resume_reading()
                else: yield None

            await sleep(0)

    async def push(app, data: (bytes, bytearray)):
        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

class BlazeioClientProtocolBuffered(BufferedProtocol):
    __slots__ = (
        '__is_at_eof__',
        '__is_alive__',
        'transport',
        '__buff__',
        '__nbytes__',
        'buff_len',
        'sizehint',
    )

    def __init__(app):
        app.buff_len = 1024
        app.__buff__ = bytearray(app.buff_len)
        app.__nbytes__ = app.buff_len
        app.__is_at_eof__ = False
        app.sizehint = 0

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
        app.__nbytes__ = nbytes

    async def pull(app, buff_len=None):
        if buff_len:
            app.buff_len = buff_len
            app.__buff__ = bytearray(app.buff_len)

        app.transport.resume_reading()

        while not app.__is_at_eof__ and not app.transport.is_closing():
            if app.transport.is_reading():
                await sleep(0)
                continue

            chunk, app.__buff__[:app.__nbytes__] = bytes(memoryview(app.__buff__)[:app.__nbytes__]), bytearray(app.buff_len)
            
            if chunk != bytes(bytearray(app.buff_len)):
                yield chunk

            app.transport.resume_reading()

    def get_buffer(app, sizehint):
        app.sizehint = sizehint
        if sizehint > len(app.__buff__):
            app.__buff__ += bytearray(sizehint - len(app.__buff__))

        return memoryview(app.__buff__)[: sizehint or app.buff_len]

    async def push(app, data: (bytes, bytearray)):
        if not app.transport.is_closing():
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

ssl_context = create_default_context()

class Session:
    __slots__ = ("transport", "protocol", "args", "kwargs", "host", "port", "path", "headers", "buff", "method", "content_length", "received_len", "response_headers", "status_code", "proxy", "connect_only")

    def __init__(app, *args, **kwargs):
        app.args, app.kwargs = args, kwargs
        app.response_headers = defaultdict(str)
        app.status_code = 0

    async def url_to_host(app, url: str):
        parsed_url = urlparse(url)
        host = parsed_url.hostname

        path = parsed_url.path
        port = parsed_url.port
        
        if parsed_url.query:
            path += "?%s" % parsed_url.query

        if not port:
            if url.startswith("https"):
                port = 443
            else:
                port = 80

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

    async def create_connection(app, url: str = "", method: str = "", headers: dict = {}, connect_only: bool = False, host = 0, port: int = 0, path: str = "", content = None, proxy={}, **kwargs):
        app.method = method
        app.headers = dict(headers)
        app.proxy = proxy
        app.connect_only = connect_only

        if not host and not port:
            app.host, app.port, app.path = await app.url_to_host(url)
            if not "Host" in app.headers: app.headers["Host"] = app.host
        else:
            app.host, app.port, app.path, app.connect_only = host, port, path, True

        if not app.connect_only:
            app.transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(),
                host=app.host,
                port=app.port,
                ssl=ssl_context if app.port == 443 else None
            )
        elif app.proxy: await app.setup_proxy()

        else:
            app.transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(),
                host=app.host,
                port=app.port,
                **kwargs
            )

        if app.connect_only: return app.protocol

        if content is not None and not app.headers.get("Content-Length"):
            if not isinstance(content, (bytes, bytearray)):
                app.headers["Transfer-Encoding"] = "chunked"
            else:
                app.headers["Content-Length"] = str(len(content))

        await app.protocol.push(bytearray("%s %s HTTP/1.1\r\n" % (app.method, app.path), "utf-8"))

        for key, val in app.headers.items(): await app.protocol.push(bytearray("%s: %s\r\n" % (key, val), "utf-8"))

        await app.protocol.push(b"\r\n")
        
        if content is not None:
            if isinstance(content, (bytes, bytearray)):
                await app.protocol.push(content)
                await app.prepare_http()
                return app
            else:
                if app.headers.get("Transfer-Encoding"):
                    async for chunk in content:
                        chunk = b"%X\r\n%s\r\n" % (len(chunk), chunk)
        
                        await app.protocol.push(chunk)
                    
                    await app.protocol.push(b"0\r\n\r\n")
                else:
                    async for chunk in content:
                        if chunk: await app.protocol.push(chunk)

            await app.prepare_http()

        return app

    async def setup_proxy(app,):
        payload = b'CONNECT %s:%s HTTP/1.1\r\nProxy-Connection: keep-alive\r\n%sUser-Agent: Dalvik/2.1.0 (Linux; U; Android 12; TECNO BF6 Build/SP1A.210812.001)\r\n\r\n' % (app.host.encode(), str(app.port).encode(), b'Proxy-Authorization: Basic %s\r\n' % auth.encode() if (auth := app.proxy.get("auth")) else b'')

        app.transport, app.protocol = await loop.create_connection(
            lambda: BlazeioClientProtocol(),
            host=app.proxy.get("host"),
            port=app.proxy.get("port"),
        )
        
        await app.protocol.push(payload)

        async for chunk in app.protocol.pull():
            if chunk:
                print(chunk)
                break
        
        ctx = create_default_context(purpose=Purpose.SERVER_AUTH)
        
        print(dir(app.transport))

        app.transport._start_tls_compatible(ctx)

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