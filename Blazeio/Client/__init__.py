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
    def __init__(app, on_data_received, on_connection_lost, on_eof_received):
        app.on_data_received = on_data_received
        app.on_connection_lost = on_connection_lost
        app.on_eof_received = on_eof_received

    def connection_made(app, transport):
        app.transport = transport

    def data_received(app, data):
        app.on_data_received(data)

    def eof_received(app):
        app.on_eof_received()

    def connection_lost(app, exc):
        app.on_connection_lost(exc)

class Session:
    def __init__(app, url: str, method: str = "GET", headers: dict = {}, port:int = 443, connect_only=False, params=None):
        app.url, app.method, app.headers, app.port, app.connect_only, app.params = url, method, headers, port, connect_only, params
    
    async def __aenter__(app):
        url, method, headers, port, connect_only, params = app.url, app.method, app.headers, app.port, app.connect_only, app.params
        
        if params:
            prms = ""
            if not (i := "?") in url:
                prms += i
            else:
                prms += "&"

            for key, val in params.items():
                #await sleep(0)
                data = "%s=%s" % (str(key), str(val))
                if "=" in prms:
                    prms += "&"

                prms += data

            url += prms
        
        app.host, app.path = await app.url_to_host(url)
        
        if port == 443: app.ssl_context = create_default_context()

        app.transport = None
        app.buffer = deque()
        app.eof_received = False
        app.connection_lost = False

        def on_data_received(data): app.buffer.append(data)

        def on_connection_lost(exc): app.connection_lost = True

        def on_eof_received(): app.eof_received = True

        protocol = BlazeioClientProtocol(on_data_received, on_connection_lost, on_eof_received)
        
        loop = get_event_loop()

        app.transport, app.protocol_instance = await loop.create_connection(
            lambda: protocol,
            app.host, port, ssl=app.ssl_context if port == 443 else None
        )

        app.response_headers = None
        app.text = bytearray()
        app.sepr = b'\r\n\r\n'
        app.content_length = None
        app.actual_length = 0
        app.remaining = None
        app.perf_counter = perf_counter()

        await app.write(f"{method} {app.path} HTTP/1.1\r\n".encode())
        if not "Host" in headers:
            headers["Host"] = app.host
            
        for key, val in headers.items():
            await app.write(f"{key}: {val}\r\n".encode())
            
        await app.write("\r\n".encode())
        if connect_only: return app


        async for i in app.get_data(initial=True):
            pass

        return app

    async def url_to_host(app, url):
        #await sleep(0)
        sepr = "://"

        if (idx := url.find(sepr)) != -1:
            url = url[idx:].replace(sepr, "")

        sepr = "/"

        if (idx := url.find(sepr)) != -1:
            path = url[idx:].replace(" ", "%20")
            url = url[:idx]

        else:
            path = sepr

        return url, path

    async def write(app, chunk: (bytes, bytearray)):
        app.transport.write(chunk)

    async def stream(app):
        try:
            while True:
                if app.buffer:
                    yield app.buffer.popleft()
                else:
                    yield None

                    if app.eof_received: break
                    if app.connection_lost: break
                
                await sleep(0)

        except Exception as e:
            p("Exception: " + str(e))
            raise e

    async def get_headers(app, data):
        other_parts = data.decode("utf-8")

        if '\r\n' in other_parts:
            sepr = ': '
            headers = defaultdict(str)
            for header in other_parts.split('\r\n'):
                await sleep(0)
                if sepr in header:
                    key, val = header.split(sepr, 1)
                    headers[key.strip()] = val.strip()
            
            headers = dict(headers)
            return headers
        else:
            return

    async def get_data(app, initial=False, timeout=2):
        async for chunk in app.stream():
            if chunk:
                app.perf_counter = perf_counter()
                if app.text is not None:
                    app.text.extend(chunk)

                if not app.response_headers and app.sepr in app.text:
                    _ = app.text.split(app.sepr)
                    headers, app.remaining = _[0], app.sepr.join(_[1:])
                    chunk = app.remaining

                    app.response_headers = await app.get_headers(headers)
                    
                    if (content_length := app.response_headers.get('Content-Length')):
                        app.content_length = int(content_length)
                    else:
                        app.content_length = None

                    app.text = None
                    app.actual_length += len(chunk)
                    if initial: return
                else:
                    if app.remaining is not None:
                        yield app.remaining
                        app.remaining = None

                    yield chunk
            else:
                if app.actual_length is not None and app.content_length is not None:
                    if app.content_length <= app.actual_length:
                        break

            if chunk: app.actual_length += len(chunk)

            if app.remaining is not None:
                yield app.remaining
                app.remaining = None
            
            if perf_counter() - app.perf_counter >= float(timeout): break

    async def __aexit__(app, exc_type, exc_val, exc_tb):
        try:
            app.transport.close()
        except SSLError as e:
            return
        except Exception as e:
            p("Exception: " + str(e))
