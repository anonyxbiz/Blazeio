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
    def __init__(app, *args, **kwargs):
        app.buffer = deque()
        app.response_headers = defaultdict(str)
        app.__is_at_eof__ = False
        app.__is_connection_lost__ = False
        app.transport = None

    def connection_made(app, transport):
        app.transport = transport

    def data_received(app, data):
        app.buffer.append(data)

    def eof_received(app):
        app.__is_at_eof__ = True

    def connection_lost(app, exc=None):
        # app.transport.close()
        app.__is_connection_lost__ = True

    async def push(app, chunk):
        if not isinstance(chunk, (bytes, bytearray)):
            chunk = chunk.encode()

        if not app.__is_connection_lost__:
            app.transport.write(chunk)
        else:
            raise Err("Client has disconnected")

    async def pull(app, timeout=1):
        while app.transport is None: await sleep(0)
        endl = b"\r\n0\r\n\r\n"
        start_time = None

        while True:
            if app.buffer:
                if app.transport.is_reading(): app.transport.pause_reading()
                
                while app.buffer:
                    buff = app.buffer.popleft()
                    yield buff
                    await sleep(0)

                if endl in buff: break
                
                if not app.transport.is_reading(): app.transport.resume_reading()
                
                start_time = perf_counter()
            else:
                if start_time is not None:
                    if perf_counter() - float(start_time) >= timeout:
                        break

                if app.__is_connection_lost__: break

                yield None
            
            await sleep(0)

        app.transport.close()

    async def pull_(app, all=False, timeout=2):
        if all:
            yield b"" + app.__all__

        else:
            if app.remaining:
                chunk = b"" + app.remaining
                yield chunk
                app.__pulled_length__ += len(app.remaining)

        endl = b"\r\n0\r\n\r\n"

        while True:
            while app.buffer:
                chunk = app.buffer.popleft()
                yield chunk

                if endl in chunk:
                    app.__is_at_eof__ = True

            if app.__is_connection_lost__:
                break
            if app.__is_at_eof__:
                break

            yield None
            await sleep(0)

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
    def __init__(app, **kwargs):
        app.protocols = deque()
        app.ssl_context = create_default_context()

    async def fetch(app,
        url: str,
        method: str = "GET",
        headers = None,
        connect_only=False,
        params=None,
        body=None
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

        await protocol.push(f"{method} {path} HTTP/1.1\r\n")

        if not "Host" in _headers_:
            _headers_["Host"] = host
        
        if body and not "Content-Length" in _headers_:
            _headers_["Content-Length"] = len(body)
            
        for key, val in _headers_.items():
            await protocol.push(f"{key}: {val}\r\n".encode())

        await protocol.push("\r\n".encode())
        
        if connect_only: return protocol

        if method in ["GET", "HEAD", "OPTIONS"]:
            await protocol.fetch_headers()
        else:
            if body:
                await protocol.push(body)
                await protocol.fetch_headers()

        return protocol

    async def url_to_host(app, url: str):
        sepr = "://"
        sepr2 = ":"
        sepr3 = "/"
        host = url
        port = None
        
        if "https" in host:
            port = 443
        else:
            port = 80

        if sepr in host:
            host = host.split(sepr)[-1]

        if sepr2 in host:
            _ = host.split(sepr2)
            host, port_ = _[0], _[1]

            if sepr3 in port_:
                port_ = port_.split(sepr3)
            
            if 1:
                try:
                    port = int(port_[0])
                except Exception as e:
                    pass
                
                
        
        if sepr3 in host:
            host = host.split(sepr3)[0]
        
        if sepr3 in url and len((_ := url.split(sepr3))) >= 3:
            path = sepr3 + sepr3.join(_[3:])
        else:
            path = sepr3
        
        return host, port, path

    async def close(app):
        return
        try:
            while app.protocols:
                prot = app.protocols.popleft()
                prot.transport.close()
                
        except SSLError as e:
            return
        except Exception as e:
            p("Exception: " + str(e))
