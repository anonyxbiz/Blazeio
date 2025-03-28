# Blazeio.Client
from ..Dependencies import *
from ..Modules.request import *
from collections.abc import Iterable
from .protocol import *
from .tools import *

from ssl import create_default_context, SSLError, Purpose

ssl_context = create_default_context()

class Gen:
    __slots__ = ()
    def __init__(app):
        pass
    
    @classmethod
    async def file(app, file_path: str, chunk_size: int = 1024):
        async with async_open(file_path, "rb") as f:
            while (chunk := await f.read(chunk_size)): yield chunk

    @classmethod
    async def echo(app, x): yield x

class Session(Toolset):
    __slots__ = ("transport", "protocol", "args", "kwargs", "host", "port", "path", "headers", "buff", "method", "content_length", "received_len", "response_headers", "status_code", "proxy", "timeout", "json_payload", "handler", "decoder", "decode_resp", "write",)

    def __init__(app, *args, **kwargs):
        for key in app.__slots__:
            setattr(app, key, None)
        app.args, app.kwargs = args, kwargs
        for i in app.__class__.__bases__: i.__init__(app)

    async def __aenter__(app):
        return await app.create_connection(*app.args, **app.kwargs)

    async def conn(app, *args, **kwargs):
        if args: app.args = args
        if kwargs: app.kwargs = kwargs

        return await app.create_connection(*app.args, **app.kwargs)

    async def prepare(app, *args, **kwargs):
        if args: app.args = args
        if kwargs: app.kwargs = kwargs

        return await app.create_connection(*app.args, **app.kwargs)

    async def __aexit__(app, exc_type=None, exc_value=None, traceback=None):
        app.protocol.transport.close()

    async def url_to_host(app, url: str, scheme_sepr: str = "://", host_sepr: str = "/", param_sepr: str = "?", port_sepr: str = ":"):
        parsed_url = {}
        
        url = url.replace(r"\/", "/")
        
        if (idx := url.find(scheme_sepr)) != -1:
            parsed_url["hostname"] = url[idx + len(scheme_sepr):]
            
            if not host_sepr in parsed_url["hostname"]:
                parsed_url["hostname"] += host_sepr

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
        
        return host, port, path

    async def create_connection(
        app,
        url: str = "",
        method: str = "",
        headers: dict = {},
        connect_only: bool = False,
        host: int = 0,
        port: int = 0,
        path: str = "",
        content = None,
        proxy={},
        add_host=True,
        timeout=10.0,
        json: dict = {},
        response_headers: dict = {},
        body = None,
        decode_resp = True,
        **kwargs
    ):
        for key, val in locals().items():
            if not key in app.__slots__: continue
            if isinstance(val, dict): val = dict(val)
            
            if key == "json":
                key = "json_payload"

            setattr(app, key, val)

        if body: content = body

        if any([not host, not port]):
            app.host, app.port, app.path = await app.url_to_host(url)
        else:
            app.host, app.port, app.path = host, port, path

        if not app.protocol and not connect_only:
            app.transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**kwargs),
                host=app.host,
                port=app.port,
                ssl=ssl_context if app.port == 443 else None,
            )

        elif not app.protocol:
            app.transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**{a:b for a,b in kwargs.items() if a in BlazeioClientProtocol.__slots__}),
                host=app.host,
                port=app.port,
                **{a:b for a,b in kwargs.items() if a not in BlazeioClientProtocol.__slots__ and a not in app.__slots__}
            )
            if not app.write:
                if app.headers.get("Transfer-Encoding"): app.write = app.write_chunked
                else:
                    app.write = app.protocol.push

            return app

        if not app.write:
            if app.headers.get("Transfer-Encoding"): app.write = app.write_chunked
            else:
                app.write = app.protocol.push

        if app.json_payload:
            content = dumps(app.json_payload).encode()
            app.headers["Content-Length"] = len(content)

        if content is not None and not app.headers.get("Content-Length") and app.method not in {"GET", "HEAD", "OPTIONS"}:
            if not isinstance(content, (bytes, bytearray)):
                app.headers["Transfer-Encoding"] = "chunked"
            else:
                app.headers["Content-Length"] = str(len(content))

        if add_host:
            if not all(h in app.headers for h in ["Host", "authority", ":authority", "X-Forwarded-Host"]): app.headers["Host"] = app.host

        http_version = "1.1"

        payload = bytearray("%s %s HTTP/%s\r\n" % (app.method, app.path, http_version), "utf-8")

        for key, val in app.headers.items(): payload.extend(b"%s: %s\r\n" % (str(key).encode(), str(val).encode()))

        payload.extend(b"\r\n")

        await app.protocol.push(payload)

        if content is not None:
            if app.headers.get("Content-Length"):
                if isinstance(content, (bytes, bytearray)):
                    await app.protocol.push(content)
                else:
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

                await app.protocol.prepend(buff)
                break

        while headers and (idx := headers.find(sepr1)):
            await sleep(0)

            if idx != -1: header, headers = headers[:idx], headers[idx + len(sepr1):]
            else: header, headers = headers, bytearray()

            if (idx := header.find(sepr2)) == -1:
                if not app.status_code:
                    app.status_code = header[header.find(b" "):].decode("utf-8").strip()
                    try:
                        app.status_code = int(app.status_code[:app.status_code.find(" ")].strip())
                    except Exception as e:
                        await Log.critical("%s >> %s" % (str(e), app.status_code))

                continue
            
            key, value = header[:idx].decode("utf-8").lower(), header[idx + len(sepr2):].decode("utf-8")

            if key in app.response_headers:
                if not isinstance(app.response_headers[key], list):
                    app.response_headers[key] = [app.response_headers[key]]

                app.response_headers[key].append(value)
                continue

            app.response_headers[key] = value

        app.response_headers = dict(app.response_headers)
        app.received_len, app.content_length = 0, int(app.response_headers.get('content-length',  0))
        
        if app.response_headers.get("transfer-encoding"):
            app.handler = app.handle_chunked
        elif app.response_headers.get("content-length"):
            app.handler = app.handle_raw
        else:
            app.handler = app.protocol.pull
        
        if app.decode_resp:
            if (encoding := app.response_headers.pop("content-encoding", None)):
                if encoding == "br":
                    app.decoder = app.brotli
                elif encoding == "gzip":
                    app.decoder = app.gzip
                else:
                    app.decoder = None
            else:
                app.decoder = None

    async def handle_chunked(app, endsig =  b"0\r\n\r\n", sepr1=b"\r\n",):
        end, buff = False, bytearray()
        read, size, idx = 0, False, -1

        async for chunk in app.protocol.ayield(app.timeout):
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

    async def handle_raw(app):
        async for chunk in app.protocol.ayield(app.timeout):
            if app.received_len >= app.content_length: break

            if not chunk: continue
            app.received_len += len(chunk)

            yield chunk

    async def pull(app, http=True):
        if http and not app.response_headers:
            await app.prepare_http()
        
        if not app.decoder:
            async for chunk in app.handler():
                if chunk:
                    yield chunk
        else:
            async for chunk in app.decoder():
                if chunk:
                    yield chunk

    async def aread(app, decode=False):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)

        return data if not decode else data.decode("utf-8")

    async def text(app):
        return await app.aread(True)

    async def push(app, *args):
        return await app.protocol.push(*args)

    async def ayield(app, *args):
        async for chunk in app.protocol.ayield(*args): yield chunk

if __name__ == "__main__":
    pass