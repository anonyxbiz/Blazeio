# Blazeio.Client
from ..Dependencies import *
from ..Dependencies.alts import *
from ..Modules.request import *
from ..Protocols.client_protocol import *

__memory__ = {}

class Gen:
    __slots__ = ()
    def __init__(app):
        pass
    
    @classmethod
    async def file(app, file_path: str, chunk_size: (bool, int) = None):
        if not chunk_size: chunk_size = ioConf.OUTBOUND_CHUNK_SIZE

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
    __slots__ = ("protocol", "args", "kwargs", "host", "port", "path", "buff", "content_length", "content_type", "received_len", "response_headers", "status_code", "proxy", "timeout", "handler", "decoder", "decode_resp", "write", "max_unthreaded_json_loads_size", "params", "proxy_host", "proxy_port", "follow_redirects", "auto_set_cookies", "reason_phrase", "consumption_started", "decompressor", "compressor", "url_to_host", "prepare_failures", "has_sent_headers", "loop", "close_on_exit",)

    __should_be_reset__ = ("decompressor", "compressor", "has_sent_headers",)

    NON_BODIED_HTTP_METHODS = {
        "GET", "HEAD", "OPTIONS", "DELETE"
    }
    not_stated = "response_headers"

    __important_headers__ = ("Content-length", "Transfer-encoding", "Content-encoding", "Content-type", "Cookies", "Host")
    
    known_ext_types = (BlazeioException, KeyboardInterrupt, CancelledError, RuntimeError, str)

    def __init__(app, *args, **kwargs):
        for key in app.__slots__: setattr(app, key, None)
        app.loop = kwargs.pop("evloop", None)
        app.args, app.kwargs = args, kwargs

    def __getattr__(app, name):
        if (method := getattr(app.protocol, name, None)):
            pass
        elif (val := StaticStuff.dynamic_attrs.get(name)):
            method = getattr(app, val)
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

        return method

    async def __aenter__(app, create_connection = True):
        if not app.loop:
            app.loop = get_event_loop()

        if app.protocol: return app

        return await app.create_connection(*app.args, **app.kwargs) if create_connection else create_connection

    def conn(app, *a, **k): return app.prepare(*args, **kwargs)

    async def prepare(app, *args, **kwargs):
        if app.close_on_exit != False:
            app.close_on_exit = False

        if app.has_sent_headers and not app.is_prepared() and not app.protocol.transport.is_closing(): return app

        if args: app.args = (*args, *app.args[len(args):])
        if kwargs: app.kwargs.update(kwargs)

        return await app.create_connection(*app.args, **app.kwargs)

    async def __aexit__(app, exc_type=None, exc_value=None, traceback=None):
        known = isinstance(exc_value, app.known_ext_types)

        if (on_exit_callback := app.kwargs.get("on_exit_callback")):
            func = on_exit_callback[0]
            if len(on_exit_callback) > 1:
                args = (app, *on_exit_callback[1:])
            else:
                args = (app,)

            await func(*args) if iscoroutinefunction(func) else func(*args)

        if not known:
            if exc_type or exc_value or traceback:
                await plog.b_red(app.__class__.__name__, "\nException occured in %s.\nLine: %s.\nfunc: %s.\nCode Part: `%s`.\nexc_type: %s.\ntext: %s.\n" % (*extract_tb(traceback)[-1], str(exc_type), exc_value))

        if isinstance(exc_value, BlazeioException):
            raise exc_value

        if not isinstance(exc_value, CancelledError):
            if app.close_on_exit == False: return True

        if (protocol := getattr(app, "protocol", None)): protocol.transport.close()

        return False

    def form_urlencode(app, form: dict):
        return "&".join(["%s=%s" % (key, form[key]) for key in form]).encode()

    async def create_connection(app, url: (str, None) = None, method: (str, None) = None, headers: dict = {}, connect_only: bool = False, host: (int, None) = None, port: (int, None) = None, path: (str, None) = None, content: (tuple[bool, AsyncIterable[bytes | bytearray]] | None) = None, proxy: (tuple,dict) = {}, add_host: bool = True, timeout: float = 30.0, json: dict = {}, cookies: dict = {}, response_headers: dict = {}, params: dict = {}, body: (bool, bytes, bytearray) = None, stream_file: (None, tuple) = None, decode_resp: bool = True, max_unthreaded_json_loads_size: int = 102400, follow_redirects: bool = False, auto_set_cookies: bool = False, status_code: int = 0, form_urlencoded: (None, dict) = None, multipart: (None, dict) = None, **kwargs):
        __locals__ = locals()
        for key in app.__slots__:
            if (val := __locals__.get(key, NotImplemented)) == NotImplemented: continue
            if isinstance(val, dict): val = dict(val)
            elif isinstance(val, list): val = list(val)
            setattr(app, key, val)

        stdheaders = dict(headers)

        if app.protocol:
            if app.protocol.__stream__: app.protocol.__stream__.clear()

            for key in app.__should_be_reset__: setattr(app, key, None)

            if app.protocol.transport.is_closing():
                app.protocol = None

            proxy = None

        if method:
            method = method.upper()

        if not host and not port:
            app.host, app.port, app.path = ioConf.url_to_host(url, app.params)

        normalized_headers = DictView(stdheaders)

        for i in app.__important_headers__:
            if i in normalized_headers and i not in stdheaders:
                stdheaders[i] = normalized_headers.pop(i)

        if multipart:
            multipart = Multipart(**multipart)
            stdheaders.update(multipart.headers)
            content = multipart.pull()

        if "client_protocol" in kwargs:
            client_protocol = kwargs.pop("client_protocol")
        else:
            client_protocol = BlazeioClientProtocol

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

        if form_urlencoded:
            body = app.form_urlencode(form_urlencoded)
            normalized_headers["Content-type"] = "application/x-www-form-urlencoded"

        if json:
            body = dumps(json).encode()
            normalized_headers["Content-type"] = "application/json"

        if body:
            normalized_headers["Content-length"] = str(len(body))

        if (content is not None or body is not None) and not "Content-length" in normalized_headers and not "Transfer-encoding" in normalized_headers and method not in {"GET", "HEAD", "OPTIONS", "CONNECT", "DELETE"}:
            if not isinstance(content, (bytes, bytearray)):
                normalized_headers["Transfer-encoding"] = "chunked"
            else:
                normalized_headers["Content-length"] = str(len(content))

        if proxy: await app.proxy_config(stdheaders, proxy)
        ssl = ssl_context if app.port == 443 else kwargs.get("ssl", None)

        if app.proxy_port:
            ssl = ssl_context if app.proxy_port == 443 else None

        if "Content-length" in normalized_headers and normalized_headers.get(i := "Transfer-encoding"):
            normalized_headers.pop(i)

        remote_host, remote_port = app.proxy_host or app.host, app.proxy_port or app.port

        if not app.protocol and not connect_only:
            transport, app.protocol = await app.loop.create_connection(
                lambda: client_protocol(evloop=app.loop, **kwargs),
                host=remote_host,
                port=remote_port,
                ssl=ssl,
            )
        elif not app.protocol and connect_only:
            transport, app.protocol = await app.loop.create_connection(
                lambda: client_protocol(evloop=app.loop, **{a:b for a,b in kwargs.items() if a in client_protocol.__slots__}),
                host=app.host,
                port=app.port,
                ssl=ssl if not kwargs.get("ssl") else kwargs.get("ssl"),
                **{a:b for a,b in kwargs.items() if a not in client_protocol.__slots__ and a not in app.__slots__ and a != "ssl"}
            )

            return app

        payload = ioConf.gen_payload(method if not proxy else "CONNECT", stdheaders, app.path, str(app.port))

        if body: payload += body

        await app.protocol.push(payload)

        if not app.write:
            if "Transfer-encoding" in normalized_headers: app.write = app.write_chunked
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
            for callback in callbacks: await callback(app) if iscoroutinefunction(callback) else callback(app)
        
        app.has_sent_headers = True

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

class __SessionPool__:
    __slots__ = ("sessions", "loop", "max_conns", "max_contexts",)
    def __init__(app, evloop = None, max_conns = 100, max_contexts = 2):
        app.sessions, app.loop, app.max_conns, app.max_contexts = {}, evloop or ioConf.loop, max_conns, max_contexts

    async def release(app, session, context):
        async with context:
            context.notify(1)
    
    def create_instance(app, url, *args, **kwargs):
        instance = {}
        instance["context"] = ioCondition()
        kwargs.update(dict(on_exit_callback = (app.release, instance["context"])))

        instance["session"] = Session(url, *args, **kwargs)

        return instance

    async def get(app, url, *args, **kwargs):
        host, port, path = ioConf.url_to_host(url, {})

        if not (instances := app.sessions.get(key := (host, port))):
            if len(app.sessions) >= app.max_conns:
                inst = app.sessions.pop(list(app.sessions.keys())[-1])
                inst["session"].close_on_exit = True
                await inst["context"].wait()
                await inst["session"].__aenter__(create_connection = False)
                await inst["session"].__aexit__()

            app.sessions[key] = (instances := [])
            instances.append(instance := app.create_instance(url, *args, **kwargs))
        else:
            for instance in instances:
                if instance["context"].event.is_set(): break
                else: instance = None

            if not instance:
                if len(instances) < app.max_contexts:
                    instances.append(instance := app.create_instance(url, *args, **kwargs))
                else:
                    waiters = [i["context"].waiter_count for i in instances]
                    instance = instances[waiters.index(min(waiters))]

        if (not instance["session"].protocol) or (instance["session"].protocol and not instance["session"].protocol.transport.is_closing()):
            async with instance["context"]:
                await instance["context"].wait()

        return instance["session"]

class SessionPool:
    __slots__ = ("pool", "args", "kwargs", "session", "max_conns", "connection_made_callback", "pool_memory", "max_contexts",)
    def __init__(app, *args, max_conns = 100, max_contexts = 1, connection_made_callback = None, pool_memory = None, **kwargs):
        app.max_conns, app.max_contexts, app.connection_made_callback, app.pool_memory = max_conns, max_contexts, connection_made_callback, pool_memory

        app.pool, app.args, app.kwargs = app.get_pool(), args, kwargs

    def get_pool(app):
        if (pool_memory := app.pool_memory) is None and (pool_memory := __memory__.get("SessionPool", None)) is None:
            __memory__["SessionPool"] = (pool_memory := {})

        if not (pool := pool_memory.get("pool")):
            pool_memory["pool"] = (pool := __SessionPool__(max_conns=app.max_conns, max_contexts=app.max_contexts))

        return pool

    async def __aenter__(app):
        app.session = await app.pool.get(*app.args, **app.kwargs)

        if app.connection_made_callback: app.connection_made_callback()

        await app.session.__aenter__(create_connection = False)

        return await app.session.prepare(*app.args, **app.kwargs)
    
    async def exit(app):
        return await sleep(0)

    async def __aexit__(app, *args, **kwargs):
        await app.session.__aexit__(*args, **kwargs)

        return await app.exit()
        
class createSessionPool:
    __slots__ = ("pool", "pool_memory", "max_conns", "max_contexts",)
    def __init__(app, max_conns: int = 100, max_contexts: int = 2):
        app.pool_memory, app.max_conns, app.max_contexts = {}, max_conns, max_contexts

    def Session(app, *a, **k): return app.SessionPool(*a, **k)

    def SessionPool(app, *a, **k):
        return SessionPool(*a, max_conns = app.max_conns, max_contexts = app.max_contexts, pool_memory = app.pool_memory, **k)

if __name__ == "__main__":
    pass