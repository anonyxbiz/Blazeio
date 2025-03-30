# Blazeio.Client
from ..Dependencies import *
from ..Modules.request import *
from .protocol import *
from .tools import *

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

class SessionMethodSetter(type):
    HTTP_METHODS = {
        "GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH", "TRACE", "CONNECT"
    }

    def __getattr__(app, name):
        if (method := name.upper()) in app.HTTP_METHODS:
            @asynccontextmanager
            async def dynamic_method(*args, **kwargs):
                async with app.method_setter(method, *args, **kwargs) as instance:
                    yield instance
        else:
            dynamic_method = None

        if dynamic_method:
            setattr(app, name, dynamic_method)
            return dynamic_method
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

class Session(Pushtools, Pulltools, Urllib, metaclass=SessionMethodSetter):
    __slots__ = ("protocol", "args", "kwargs", "host", "port", "path", "buff", "content_length", "received_len", "response_headers", "status_code", "proxy", "timeout", "handler", "decoder", "decode_resp", "write", "max_unthreaded_json_loads_size",)

    def __init__(app, *args, **kwargs):
        for key in app.__slots__: setattr(app, key, None)
        app.args, app.kwargs = args, kwargs
        for i in app.__class__.__bases__: i.__init__(app)

    async def __aenter__(app):
        return await app.create_connection(*app.args, **app.kwargs)

    async def conn(app, *args, **kwargs):
        if args: app.args = args
        if kwargs: app.kwargs = kwargs

        return await app.create_connection(*app.args, **app.kwargs)

    async def prepare(app, *args, **kwargs):
        if not app.response_headers: return

        if args: app.args = args
        if kwargs: app.kwargs = kwargs

        return await app.create_connection(*app.args, **app.kwargs)

    async def __aexit__(app, exc_type=None, exc_value=None, traceback=None):
        if (protocol := getattr(app, "protocol", None)):
            protocol.transport.close()

        if any([exc_type, exc_value, traceback]):
            await Log.critical("exc_type: %s, exc_value: %s, traceback: %s" % (exc_type, exc_value, traceback))

            return False

    async def create_connection(
        app,
        url: str = "",
        method: str = "",
        headers: dict = {},
        connect_only: bool = False,
        host: int = 0,
        port: int = 0,
        path: str = "",
        content: (tuple[bool, AsyncIterable[bytes | bytearray]] | None) = None,
        proxy: dict = {},
        add_host: bool = True,
        timeout: float = 60.0,
        json: dict = {},
        response_headers: dict = {},
        body: (bool, bytes, bytearray) = None,
        decode_resp: bool = True,
        max_unthreaded_json_loads_size: int = 102400,
        **kwargs
    ):
        for key, val in locals().items():
            if not key in app.__slots__: continue
            if isinstance(val, dict): val = dict(val)

            setattr(app, key, val)

        if body: content = Gen.echo(body)

        if any([not host, not port]):
            app.host, app.port, app.path = await app.url_to_host(url)
        else:
            app.host, app.port, app.path = host, port, path
        
        headers = {a.capitalize(): b for a,b in headers.items()}

        if not app.protocol and not connect_only:
            transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**kwargs),
                host=app.host,
                port=app.port,
                ssl=ssl_context if app.port == 443 else None,
            )

        elif not app.protocol:
            transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**{a:b for a,b in kwargs.items() if a in BlazeioClientProtocol.__slots__}),
                host=app.host,
                port=app.port,
                **{a:b for a,b in kwargs.items() if a not in BlazeioClientProtocol.__slots__ and a not in app.__slots__}
            )
            if not app.write:
                if headers.get("Transfer-encoding"): app.write = app.write_chunked
                else:
                    app.write = app.protocol.push

            return app

        if json:
            json = dumps(json).encode()
            content = Gen.echo(json)

            headers["Content-length"] = len(json)

            if (i := "Transfer-encoding") in headers: headers.pop(i, None)

        if content is not None and all([not headers.get("Content-length"), not headers.get("Transfer-encoding"), method not in {"GET", "HEAD", "OPTIONS"}]):
            if not isinstance(content, (bytes, bytearray)):
                headers["Transfer-encoding"] = "chunked"
            else:
                headers["Content-length"] = str(len(content))

        if add_host:
            if not all(h in headers for h in ["Host", "Authority", ":authority", "X-forwarded-host"]): headers["Host"] = app.host

        http_version = "1.1"
        payload = bytearray("%s %s HTTP/%s\r\n" % (method, app.path, http_version), "utf-8")

        for key, val in headers.items(): payload.extend(b"%s: %s\r\n" % (str(key).encode(), str(val).encode()))

        payload.extend(b"\r\n")

        await app.protocol.push(payload)

        if not app.write:
            if headers.get("Transfer-encoding"): app.write = app.write_chunked
            else:
                app.write = app.protocol.push

        if content is not None:
            if isinstance(content, (bytes, bytearray)):
                await app.write(content)
            elif isinstance(content, AsyncIterable):
                async for chunk in content: await app.write(chunk)
                await app.eof()
            else:
                raise Err("content must be AsyncIterable | bytes | bytearray")

            await app.prepare_http()

        return app

    @classmethod
    @asynccontextmanager
    async def method_setter(app, method: str, *args, **kwargs):
        exception = ()
        try:
            app = app(*(args[0], method, *args[1:]), **kwargs)
            yield await app.__aenter__()
        except Exception as e:
            exception = (type(e).__name__, str(e), e.__traceback__)
        finally:
            await app.__aexit__(*exception)

    @classmethod
    async def fetch(app, *args, **kwargs):
        async with app(*args, **kwargs) as instance:
            return await instance.data()

if __name__ == "__main__":
    pass