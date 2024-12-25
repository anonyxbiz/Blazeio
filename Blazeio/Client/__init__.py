# Blazeio.Client
from asyncio import Protocol, get_event_loop, new_event_loop, sleep
from time import perf_counter
from ssl import create_default_context, SSLError
from ujson import loads, dumps
from collections import deque, defaultdict

p = print

class Err(Exception):
    def __init__(app, message=None):
        super().__init__(message)
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

loop = get_event_loop()

class Utl:
    @classmethod
    async def split_before(app, str_: (bytearray, bytes, str), to_find: (bytearray, bytes, str)):
        await sleep(0)
        if (idx := str_.find(to_find)) != -1:
            return str_[:idx]
        else:
            return False

    @classmethod
    async def split_between(app, str_: (bytearray, bytes, str), to_find: (bytearray, bytes, str)):
        await sleep(0)
        if (idx := str_.find(to_find)) != -1:
            return (str_[:idx], str_[idx + len(to_find):])
        else:
            return False

    @classmethod
    async def split_after(app, str_: (bytearray, bytes, str), to_find: (bytearray, bytes, str)):
        await sleep(0)
        if (idx := str_.find(to_find)) != -1:
            return str_[idx + len(to_find):]
        else:
            return False

class BlazeioClientProtocol(Protocol):
    def __init__(app, *args, **kwargs):
        app.buffer = deque()
        app.response_headers = False
        app.__is_at_eof__ = False
        app.__is_connection_lost__ = False
        app.transport = None
        app.status_code = 0
        app.reason = None

    def connection_made(app, transport):
        app.transport = transport
        #app.transport.pause_reading()

    def data_received(app, data):
        app.buffer.append(data)

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc=None):
        app.__is_connection_lost__ = True

    async def push(app, chunk):
        if app.__is_connection_lost__:
            raise Err("Client has disconnected")
        
        app.transport.write(chunk)

    async def pull(app, timeout=5):
        endl = b"\r\n0"
        #\r\n0\r'
        if app.response_headers:
            if (cl := app.response_headers.get("Content-Length")):
                app.expected_cl = int(cl)
            else:
                app.expected_cl = app.response_headers.get("Transfer-Encoding")

            app.received_cl = 0
        else:
            app.expected_cl = False
            app.received_cl = 0
        
        start = perf_counter()
        while True:
            await sleep(0)
            if app.buffer:
                buff = app.buffer.popleft()
                
                yield buff

                if app.response_headers:
                    app.received_cl += len(buff)
            
                if endl in buff: break
                start = perf_counter()
                
            else:
                if app.expected_cl and app.expected_cl != "chunked":
                    if app.received_cl >= app.expected_cl: break
                else:
                    if perf_counter() - start >= timeout: break
                    
                if app.__is_connection_lost__: break

                yield None

            if not app.transport.is_reading(): app.transport.resume_reading()
                
        app.transport.close()

    async def fetch_headers(app, sepr = b"\r\n\r\n", head_sepr = b"\r\n"):
        tmp = bytearray()
        app.response_headers = defaultdict(str)
        
        async for data in app.pull():
            if data:
                tmp.extend(data)
                if (idx := tmp.rfind(sepr)) != -1:
                    rem = tmp[idx + len(sepr):]
                    
                    app.buffer.appendleft(rem)
                    
                    tmp = tmp[:idx]
                    break
        
        while True:
            if (idx := tmp.find(head_sepr)) != -1:
                header = tmp[:idx].decode("utf-8")
                tmp = tmp[idx+len(head_sepr):]
            else:
                header = tmp.decode("utf-8")
            
            if (idx2 := header.find(": ")) != -1:
                key, value = header[:idx2], header[idx2 + 2:]
                app.response_headers[key] = value
            else:
                _ = header.split(" ")
                
                try:app.status_code = int(_[1])
                except:pass
                
                app.reason = " ".join(_[2:])
            
            if idx == -1:
                break
                
        app.response_headers = dict(app.response_headers)
        return app.response_headers

class Session:
    def __init__(app, **kwargs):
        app.protocols = deque()
        app.ssl_context = create_default_context()

    async def fetch(app, *args, **kwargs): return await app.prepare(*args, **kwargs)

    async def url_to_host(
        app,
        url: str,
        sepr: str = "://",
        sepr2: str = ":",
        sepr3: str = "/"
    ):
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

    async def prepare(app,
        url: str,
        method: str = "GET",
        headers: dict = {},
        connect_only: bool = False,
    ):
        host, port, path = await app.url_to_host(url)

        if not headers:
            _headers_ = {}
        else:
            _headers_ = headers

        transport, protocol = await loop.create_connection(
            lambda: BlazeioClientProtocol(),
            host=host, port=port, ssl=app.ssl_context if port == 443 else None
        )

        await protocol.push(bytearray("%s %s HTTP/1.1\r\n" % (method, path), "utf-8"))

        if not "Host" in _headers_:
            _headers_["Host"] = host
            
        for key, val in _headers_.items():
            await protocol.push(bytearray("%s: %s\r\n" % (key, val), "utf-8"))

        await protocol.push(b"\r\n")
        
        #if method in ("GET", "HEAD", "OPTIONS",):
        if not connect_only:
            await protocol.fetch_headers()
        return protocol
        