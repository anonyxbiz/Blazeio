# Blazeio.Client
from ..Dependencies import *
from ..Modules.request import *
from .protocol import *
from .tools import *

class Gen:
    __slots__ = ()
    def __init__(app):
        pass
    
    @classmethod
    async def file(app, file_path: str, chunk_size: (bool, int) = None):
        if not chunk_size: chunk_size = OUTBOUND_CHUNK_SIZE

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
    __slots__ = ("protocol", "args", "kwargs", "host", "port", "path", "buff", "content_length", "received_len", "response_headers", "status_code", "proxy", "timeout", "handler", "decoder", "decode_resp", "write", "max_unthreaded_json_loads_size", "params", "proxy_host", "proxy_port", "follow_redirects", "auto_set_cookies",)

    not_stated = "response_headers"

    def __init__(app, *args, **kwargs):
        for key in app.__slots__: setattr(app, key, None)
        app.args, app.kwargs = args, kwargs

    def __getattr__(app, name):
        if (method := getattr(app.protocol, name, None)):
            pass
        elif (val := StaticStuff.dynamic_attrs.get(name)):
            method = getattr(app, val)
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

        return method

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

        if exc_type:
            if not "Client has disconnected." in str(exc_value):
                await Log.critical("exc_type: %s, exc_value: %s, traceback: %s" % (exc_type, exc_value, traceback))

        await sleep(0)

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
        proxy: (tuple,dict) = {},
        add_host: bool = True,
        timeout: float = 30.0,
        json: dict = {},
        cookies: dict = {},
        response_headers: dict = {},
        params: dict = {},
        body: (bool, bytes, bytearray) = None,
        decode_resp: bool = True,
        max_unthreaded_json_loads_size: int = 102400,
        follow_redirects: bool = False,
        auto_set_cookies: bool = False,
        proxy_host: str = "",
        proxy_port: int = 0,

        **kwargs
    ):
        async for key, val in Async.ite(locals()):
            if not key in app.__slots__: continue
            if isinstance(val, dict): val = dict(val)

            setattr(app, key, val)

        if body: content = Gen.echo(body)

        if not host or not port:
            app.host, app.port, app.path = await app.url_to_host(url, app.params)
        else:
            app.host, app.port, app.path = host, port, path

        headers = {key.capitalize(): val async for key, val in Async.ite(headers)}

        if cookies:
            app.kwargs["cookies"] = cookies
            cookie = ""
            async for key, val in Async.ite(cookies):
                cookie += "%s%s=%s" % ("; " if cookie else "", key, val)

            headers["Cookie"] = cookie

        if app.protocol:
            proxy = None

        if proxy: await app.proxy_config(headers, proxy)
        
        ssl = ssl_context if app.port == 443 else None
        
        if app.proxy_port:
            ssl = ssl_context if app.proxy_port == 443 else None

        remote_host, remote_port = app.proxy_host or app.host, app.proxy_port or app.port

        if not app.protocol and not connect_only:
            transport, app.protocol = await loop.create_connection(
                lambda: BlazeioClientProtocol(**kwargs),
                host=remote_host,
                port=remote_port,
                ssl=ssl,
            )

        elif not app.protocol and connect_only:
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

        if add_host:
            if not all(h in headers for h in ["Host", "Authority", ":authority", "X-forwarded-host"]): headers["Host"] = app.host

        if json:
            json = dumps(json).encode()
            content = Gen.echo(json)

            headers["Content-length"] = len(json)

            if (i := "Transfer-encoding") in headers: headers.pop(i, None)

        if content is not None and all([not headers.get("Content-length"), not headers.get("Transfer-encoding"), method not in {"GET", "HEAD", "OPTIONS", "CONNECT"}]):
            if not isinstance(content, (bytes, bytearray)):
                headers["Transfer-encoding"] = "chunked"
            else:
                headers["Content-length"] = str(len(content))

        await app.protocol.push(await app.gen_payload(method if not proxy else "CONNECT", headers, app.path))

        if not app.write:
            if headers.get("Transfer-encoding"): app.write = app.write_chunked
            else:
                app.write = app.push

        if content is not None:
            if isinstance(content, (bytes, bytearray)):
                await app.write(content)
            elif isinstance(content, AsyncIterable):
                async for chunk in content: await app.write(chunk)
                await app.eof()
            else:
                raise Err("content must be AsyncIterable | bytes | bytearray")

            await app.prepare_http()

        if proxy:
            await app.prepare_connect(method, headers)

        return app

    async def gen_payload(app, method: str, headers: dict, path: str, http_version = "1.1"):
        if method not in ["CONNECT"]:
            payload = bytearray("%s %s HTTP/%s\r\n" % (method.upper(), path, http_version), "utf-8")
        else:
            payload = bytearray("%s %s:%s HTTP/%s\r\n" % (method.upper(), app.host, app.port, http_version), "utf-8")

        async for key, val in Async.ite(headers):
            payload.extend(bytearray("%s: %s\r\n" % (key, val), "utf-8"))

        payload.extend(b"\r\n")

        return payload

    async def proxy_config(app, headers, proxy):
        if isinstance(proxy, dict):
            if not (proxy_host := proxy.get("host")) or not (proxy_port := proxy.get("port")):
                raise Err("Proxy dict must have `host` and `port`.")

                app.proxy_host, app.proxy_port = proxy_host, proxy_port
    
            if (username := proxy.get("username")) and (password := proxy.get("password")):
                pass

        elif isinstance(proxy, tuple):
            if (proxy_len := len(proxy)) not in (2,4):
                raise Err("Proxy tuple must be either 2 or 4")

            if proxy_len == 2:
                app.proxy_host, app.proxy_port = proxy

            elif proxy_len == 4:
                app.proxy_host, app.proxy_port, username, password  = proxy
        
        app.proxy_port = int(app.proxy_port)

        auth = b64encode(str("%s:%s" % (username, password)).encode()).decode()
        headers["Proxy-Authorization"] = "Basic %s\r\n" % auth

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
    async def fetch(app,*args, **kwargs):
        async with app(*args, **kwargs) as instance:
            return await instance.data()

class DynamicRequestResponse(type):
    response_types = {"text", "json"}

    def __getattr__(app, name):
        if (response_type := name.lower()) in app.response_types:
            async def dynamic_method(*args, **kwargs):
                return await app.requestify(response_type, args, kwargs)
        else:
            dynamic_method = None

        if dynamic_method:
            setattr(app, name, dynamic_method)
            return dynamic_method
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

class __Request__(metaclass=DynamicRequestResponse):
    def __init__(app): pass

    @classmethod
    async def requestify(app, response_type: str, args, kwargs):
        async with Session(*args, **kwargs) as instance:
            return await getattr(instance, response_type)()

Session.request = __Request__

if __name__ == "__main__":
    pass