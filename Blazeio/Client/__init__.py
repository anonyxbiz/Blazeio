# Blazeio.Client
from ..Dependencies import *
from ..Dependencies.alts import *
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

class Session(Pushtools, Pulltools, metaclass=SessionMethodSetter):
    __slots__ = ("protocol", "args", "kwargs", "host", "port", "path", "buff", "content_length", "received_len", "response_headers", "status_code", "proxy", "timeout", "handler", "decoder", "decode_resp", "write", "max_unthreaded_json_loads_size", "params", "proxy_host", "proxy_port", "follow_redirects", "auto_set_cookies", "reason_phrase", "consumption_started", "decompressor", "compressor", "url_to_host",)

    __should_be_reset__ = ("decompressor", "compressor",)
    NON_BODIED_HTTP_METHODS = {
        "GET", "HEAD", "OPTIONS", "DELETE"
    }
    not_stated = "response_headers"

    __important_headers__ = ("Content-length", "Transfer-encoding", "Content-encoding", "Content-type", "Cookies", "Host")

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

    def conn(app, *args, **kwargs):
        if not app.response_headers: return sleep(0)
        if args: app.args = (*args, *app.args[len(args):])
        if kwargs: app.kwargs.update(kwargs)

        for key in app.__should_be_reset__: setattr(app, key, None)

        return app.create_connection(*app.args, **app.kwargs)
    
    def prepare(app, *args, **kwargs):
        if app.protocol: app.protocol.__stream__.clear()

        if not app.response_headers: return sleep(0)

        if args: app.args = (*args, *app.args[len(args):])
        if kwargs: app.kwargs.update(kwargs)

        for key in app.__should_be_reset__: setattr(app, key, None)

        return app.create_connection(*app.args, **app.kwargs)

    async def __aexit__(app, exc_type=None, exc_value=None, traceback=None):
        if not isinstance(exc_type, ServerDisconnected):
            if (protocol := getattr(app, "protocol", None)):
                protocol.transport.close()

            if exc_type or exc_value or traceback:
                if all([not i in str(exc_value) and not i in str(exc_type) for i in ("KeyboardInterrupt","Client has disconnected.", "CancelledError")]):
                    filename, lineno, func, text = extract_tb(traceback)[-1]
                    await log.critical("\nException occured in %s.\nLine: %s.\nCode Part: `%s`.\nfunc: %s.\ntext: %s.\n" % (filename, lineno, text, func, str(exc_value)))

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
        stream_file: (None, tuple) = None,
        decode_resp: bool = True,
        max_unthreaded_json_loads_size: int = 102400,
        follow_redirects: bool = False,
        auto_set_cookies: bool = False,
        status_code: int = 0,
        **kwargs
    ):
        __locals__ = locals()
        for key in app.__slots__:
            if (val := __locals__.get(key, NotImplemented)) == NotImplemented: continue
            if isinstance(val, dict): val = dict(val)
            elif isinstance(val, list): val = list(val)
            setattr(app, key, val)

        stdheaders = dict(headers)

        if app.protocol and app.protocol.transport.is_closing():
            app.protocol = None

        if app.protocol: proxy = None

        method = method.upper()

        app.host, app.port, app.path = ioConf.url_to_host(url, app.params)

        normalized_headers = DictView(stdheaders)

        for i in app.__important_headers__:
            if i in normalized_headers and i not in stdheaders:
                stdheaders[i] = normalized_headers.pop(i)

        if (multipart := kwargs.get("multipart")):
            multipart = Multipart(**multipart)
            stdheaders.update(multipart.headers)
            content = multipart.pull()

        if stream_file:
            normalized_headers["Content-length"] = str(os_path.getsize(stream_file[0]))
            if (content_type := guess_type(stream_file[0])[0]):
                normalized_headers["Content-type"] = content_type

            content = Gen.file(*stream_file)

        if cookies:
            app.kwargs["cookies"] = cookies
            cookie = ""
            normalized_cookies = DictView(cookies)

            for key, val in normalized_cookies.items():
                cookie += "%s%s=%s" % ("; " if cookie else "", key, val)

            normalized_headers["Cookie"] = cookie

        if add_host:
            if not all([h in normalized_headers for h in ["Host", "Authority", ":authority", "X-forwarded-host"]]):
                normalized_headers["Host"] = app.host

        if json:
            body = dumps(json).encode()
            if not 'Content-type' in normalized_headers:
                normalized_headers["Content-type"] = "application/json"

            if (i := "Transfer-encoding") in normalized_headers: normalized_headers.pop(i)

        if body:
            normalized_headers["Content-length"] = str(len(body))
            if (i := "Transfer-encoding") in normalized_headers: normalized_headers.pop(i)

        if (content is not None or body is not None) and not "Content-length" in stdheaders and not "Transfer-encoding" in stdheaders and method not in {"GET", "HEAD", "OPTIONS", "CONNECT", "DELETE"}:
            if not isinstance(content, (bytes, bytearray)):
                normalized_headers["Transfer-encoding"] = "chunked"
            else:
                normalized_headers["Content-length"] = str(len(content))

        if proxy: await app.proxy_config(stdheaders, proxy)
        ssl = ssl_context if app.port == 443 else None
        if app.proxy_port:
            ssl = ssl_context if app.proxy_port == 443 else None

        remote_host, remote_port = app.proxy_host or app.host, app.proxy_port or app.port

        if not app.protocol and not connect_only:
            transport, app.protocol = await get_event_loop().create_connection(
                lambda: BlazeioClientProtocol(**kwargs),
                host=remote_host,
                port=remote_port,
                ssl=ssl,
            )
        elif not app.protocol and connect_only:
            transport, app.protocol = await get_event_loop().create_connection(
                lambda: BlazeioClientProtocol(**{a:b for a,b in kwargs.items() if a in BlazeioClientProtocol.__slots__}),
                host=app.host,
                port=app.port,
                ssl=ssl if not kwargs.get("ssl") else kwargs.get("ssl"),
                **{a:b for a,b in kwargs.items() if a not in BlazeioClientProtocol.__slots__ and a not in app.__slots__ and a != "ssl"}
            )

            return app
        
        payload = ioConf.gen_payload(method if not proxy else "CONNECT", stdheaders, app.path, str(app.port))

        if body:
            payload = payload + body

        await app.protocol.push(payload)

        if not app.write:
            if "Transfer-encoding" in stdheaders: app.write = app.write_chunked
            else:
                app.write = app.push

        if proxy:
            await app.prepare_connect(method, stdheaders)

        if content is not None:
            if isinstance(content, (bytes, bytearray)):
                await app.write(content)
            elif isinstance(content, AsyncIterable):
                async for chunk in content: await app.write(chunk)
                await app.eof()
            else:
                raise Err("content must be AsyncIterable | bytes | bytearray")

            await app.prepare_http()

        elif (method in app.NON_BODIED_HTTP_METHODS) or body:
            await app.prepare_http()

        if app.is_prepared() and (callbacks := kwargs.get("callbacks")):
            for callback in callbacks: await callback(app)

        return app

    async def proxy_config(app, headers, proxy):
        username, password = None, None
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

        if username and password:
            auth = b64encode(str("%s:%s" % (username, password)).encode()).decode()
            headers["Proxy-Authorization"] = "Basic %s\r\n" % auth

        return

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
# Session.Multipart = Multipart

if __name__ == "__main__":
    pass