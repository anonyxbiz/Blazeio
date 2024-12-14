# Blazeio.Client
from asyncio import Protocol, get_event_loop, sleep
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

class BlazeioClientProtocol(Protocol):
    def __init__(app):
        app.buffer = deque()
        app.response_headers = defaultdict(str)
        app.remaining = bytearray()
        app.__is_at_eof__ = False
        app.__is_connection_lost__ = False
        app.__pulled_length__ = 0
        app.__perf_counter__ = perf_counter()
        app.__all__ = bytearray()

    def connection_made(app, transport):
        app.transport = transport

    def data_received(app, data):
        app.buffer.append(data)

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc):
        app.__is_connection_lost__ = True

    async def push(app, chunk):
        if not isinstance(chunk, (bytes, bytearray)):
            chunk = chunk.encode()

        if not app.__is_connection_lost__:
            app.transport.write(chunk)
        
    async def pull(app, all=False, timeout=2):
        if all:
            yield b"" + app.__all__
            
        else:
            if app.remaining:
                chunk = b"" + app.remaining
                yield chunk
                app.__pulled_length__ += len(app.remaining)

        endl = b"\r\n0\r\n\r\n"

        while True:
            await sleep(0)
                
            while app.buffer:
                await sleep(0)
                chunk = app.buffer.popleft()
                yield chunk

                if endl in chunk:
                    app.__is_at_eof__ = True

            if app.__is_connection_lost__:
                break
            if app.__is_at_eof__:
                break
            
            if perf_counter() - app.__perf_counter__ >= float(timeout):
                break
            yield None

    async def fetch_headers(app):
        tmp = bytearray()
        sepr = b"\r\n\r\n"

        async for data in app.pull():
            if data:
                tmp.extend(data)
                app.__all__.extend(data)
                if sepr in tmp:
                    _ = tmp.split(sepr)
                    app.remaining.extend(sepr.join(_[1:]))

                    if (i := b'\r\n') in app.remaining:
                        app.remaining = i.join(app.remaining.split(i)[1:])

                    tmp = _[0]
                    break

        other_parts = tmp.decode("utf-8")

        if '\r\n' in other_parts:
            sepr = ': '
            for header in other_parts.split('\r\n'):
                await sleep(0)
                if sepr in header:
                    key, val = header.split(sepr, 1)
                    app.response_headers[key.strip()] = val.strip()
            
            app.response_headers = dict(app.response_headers)
        else:
            return

loop = get_event_loop()

class Session:
    def __init__(app, url: str, method: str = "GET", headers: dict = {}, port:int = 80, connect_only=False, params=None, body=None, **kwargs):
        app.__dict__.update(locals())
        app.host = app.url
        
    async def __aenter__(app):
        if app.params:
            prms = ""
            if not (i := "?") in url:
                prms += i
            else:
                prms += "&"

            for key, val in app.params.items():
                await sleep(0)
                data = "%s=%s" % (str(key), str(val))
                if "=" in prms:
                    prms += "&"

                prms += data

            app.url += prms

        await app.url_to_host()
        
        if app.port == 443:
            app.ssl_context = create_default_context()

        protocol = BlazeioClientProtocol()
        app.protocol = protocol

        transport, protocol_instance = await loop.create_connection(
            lambda: protocol,
            app.host, app.port, ssl=app.ssl_context if app.port == 443 else None
        )
        
        await app.protocol.push(f"{app.method} {app.path} HTTP/1.1\r\n".encode())

        if not "Host" in app.headers:
            app.headers["Host"] = app.host
        
        if app.body:
            app.headers["Content-Length"] = len(app.body)
            
        for key, val in app.headers.items():
            await app.protocol.push(f"{key}: {val}\r\n".encode())
            await sleep(0)
            
        await app.protocol.push("\r\n".encode())
        
        if app.connect_only: return app.protocol
        
        if app.method in ["GET", "HEAD", "OPTIONS"]:
            await app.protocol.fetch_headers()
        else:
            if app.body:
                await app.protocol.push(app.body)

                await app.protocol.fetch_headers()

        return app.protocol

    async def url_to_host(app):
        sepr = "://"
        sepr2 = ":"
        sepr3 = "/"
        
        if "https" in app.host:
            if app.port == 80: app.port = 443

        if sepr in app.host:
            app.host = app.host.split(sepr)[-1]

        if sepr2 in app.host:
            app.host, app.port = app.host.split(sepr2)
            if sepr3 in app.port:
                app.port = app.port.split(sepr3)
                try:app.port = int(app.port[0])
                except: pass
        
        if sepr3 in app.host:
            app.host = app.host.split(sepr3)[0]
        
        if sepr3 in app.url and len((_ := app.url.split(sepr3))) >= 3:
            app.path = sepr3 + sepr3.join(_[3:])
        else:
            app.path = sepr3

    async def __aexit__(app, exc_type, exc_val, exc_tb):
        try:
            app.protocol.transport.close()
        except SSLError as e:
            return
        except Exception as e:
            p("Exception: " + str(e))
