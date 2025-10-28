# Blazeio.Client
from ..Dependencies import *
from ..Dependencies.alts import *
from ..Modules.request import *
from ..Protocols.client_protocol import *
from socket import SOL_SOCKET, SO_KEEPALIVE, IPPROTO_TCP, TCP_KEEPIDLE, TCP_KEEPINTVL, inet_ntoa, inet_aton, inet_ntop, AF_INET6

__memory__ = {}

class Gen:
    __slots__ = ()
    def __init__(app):
        ...
    
    @classmethod
    async def file(app, file_path: str, chunk_size: (bool, int) = None):
        if not chunk_size: chunk_size = ioConf.OUTBOUND_CHUNK_SIZE

        async with async_open(file_path, "rb") as f:
            while (chunk := await f.read(chunk_size)): yield chunk

    @classmethod
    async def echo(app, x): yield x

class Proxyconnector:
    __slots__ = ("protocol", "proxy_type", "proxy", "connected", "tls_started")
    def __init__(app, protocol: any, proxy_type: str, proxy: dict):
        app.protocol, app.proxy_type, app.proxy, app.connected, app.tls_started = protocol, proxy_type, proxy, False, False

    def __await__(app):
        _ = yield from app.connect().__await__()
        return _

    async def connect(app):
        if app.proxy_type == "socks5":
            method = app.socks5_connect
        elif app.proxy_type == "http":
            raise ValueError("connector doesn't support %s proxy_type." % app.proxy_type)

        _ = await method()
        app.connected = True
        
        if app.proxy.get("start_tls"): await app.start_tls()

        return _

    def atyp1(app):
        return (b'\x05\x01\x02', b'\x05\x01\x00\x01%b%b' % (inet_aton(app.proxy.get("host")),  int(app.proxy.get("port")).to_bytes(2, 'big')))

    def atyp3(app):
        return (b'\x05\x01\x02', b'\x05\x01\x00\x03%b%b%b' % (int(len(app.proxy.get("host"))).to_bytes(1, "big"), app.proxy.get("host").encode(), int(app.proxy.get("port")).to_bytes(2, 'big')))

    async def socks5_connect(app):
        atyp = str(app.proxy.get("atyp", "atyp3"))
        if not (method := getattr(app, atyp, None)): raise ValueError("connector doesn't support %s atyp." % atyp)
        auth, connect = method()
        await app.protocol.writer(auth)
        await app.protocol
        await app.protocol.writer(connect)
        await app.protocol
        app.protocol.__stream__.clear()

    async def start_tls(app, context: any = None):
        app.protocol.transport = await app.protocol.loop.start_tls(app.protocol.transport, app.protocol, context or get_ssl_context(), server_hostname = app.protocol.host)
        app.tls_started = True

class BlazeioClient(BlazeioClientProtocol):
    __slots__ = ("host", "port", "args", "kwargs", "socks5proxy", "loop", "httpproxy", "proxy",)
    def __init__(app, host: str, port: int, *args, socks5proxy: (dict, None) = None, httpproxy: (dict, None) = None, loop: any = None, proxy: (Proxyconnector, None) = None, **kwargs):
        super().__init__(**{i: kwargs.pop(i) for i in BlazeioClientProtocol.expected_kwargs if i in kwargs})
        app.host, app.port, app.args, app.kwargs, app.socks5proxy, app.httpproxy, app.loop, app.proxy = host, port, args, kwargs, socks5proxy, httpproxy, loop, proxy

    async def __aenter__(app):
        await app.create_connection()
        return app

    async def __aexit__(app, *args):
        app.cancel()
        return False

    async def create_connection(app):
        if not app.loop: app.loop = get_event_loop()
        if app.socks5proxy:
            if "ssl" in app.kwargs: app.kwargs.pop("ssl")
            host, port = app.socks5proxy.get("host"), int(app.socks5proxy.get("port"))
            app.socks5proxy["host"], app.socks5proxy["port"] = app.host, app.port
            app.proxy = Proxyconnector(app, "socks5", app.socks5proxy)
        elif app.httpproxy:
            if "ssl" in app.kwargs: app.kwargs.pop("ssl")
            host, port = app.httpproxy.get("host"), int(app.httpproxy.get("port"))
            app.httpproxy["host"], app.httpproxy["port"] = app.host, app.port
            app.proxy = Proxyconnector(app, "http", app.httpproxy)
        else:
            host, port = app.host, app.port

        _ = await app.loop.create_connection(lambda: app, host, port, *app.args, **app.kwargs)

        if app.proxy and not app.proxy.connected:
            await app.proxy

        return _

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
    __slots__ = ("protocol", "args", "kwargs", "host", "port", "method", "path", "buff", "content_length", "content_type", "received_len", "response_headers", "status_code", "proxy", "timeout", "handler", "decoder", "decode_resp", "max_unthreaded_json_loads_size", "params", "proxy_host", "proxy_port", "follow_redirects", "auto_set_cookies", "reason_phrase", "consumption_started", "decompressor", "compressor", "url_to_host", "prepare_failures", "has_sent_headers", "loop", "close_on_exit", "encode_writes", "default_writer", "encoder", "eof_sent", "on_exit_callback", "chunked_encoder")

    __from_kwargs__ = (("evloop", "loop"), ("use_protocol", "protocol"), ("on_exit_callback", "on_exit_callback"))

    NON_BODIED_HTTP_METHODS = {
        "GET", "HEAD", "OPTIONS", "DELETE"
    }
    not_stated = "response_headers"

    __important_headers__ = ("Content-length", "Transfer-encoding", "Content-encoding", "Content-type", "Cookies", "Host")
    
    known_ext_types = (BlazeioException, Eof, KeyboardInterrupt, CancelledError, RuntimeError, str)

    def __init__(app, *args, **kwargs):
        for key in app.__slots__:
            setattr(app, key, None)

        for key, set_key in app.__from_kwargs__:
            if key in kwargs:
                setattr(app, set_key, kwargs.pop(key))

        app.args, app.kwargs = args, kwargs

    def __getattr__(app, key, *args):
        if hasattr(app.protocol, key):
            method = getattr(app.protocol, key)
            ...
        elif (val := StaticStuff.dynamic_attrs.get(key)):
            method = getattr(app, val)
        elif (method := app.__utilsgetattr__(key, None)):
            ...
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, key))

        return method

    def __await__(app):
        _app = yield from app.__aenter__().__await__()
        return _app
    
    def reset_protocol(app):
        if app.protocol.__stream__: app.protocol.__stream__.clear()
        if app.protocol.transport.is_closing(): app.protocol = None

    async def __aenter__(app, create_connection = True):
        if (task := current_task()):
            if not hasattr(task, "__BlazeioClientProtocol__"):
                task.__BlazeioClientProtocol__ = app

        if not app.loop:
            app.loop = get_event_loop()

        if app.protocol:
            if isinstance(app.protocol, BlazeioClientProtocol):
                return app
            elif app.kwargs.get("connect_only"):
                return app

        return await app.create_connection(*app.args, **app.kwargs) if create_connection else app

    async def __aexit__(app, exc_type=None, exc_value=None, traceback=None):
        known = isinstance(exc_value, app.known_ext_types) and not isinstance(exc_value, (Err,))
        if app.is_prepared() and app.response_headers.get("connection") == "close":
            app.protocol.transport.close()

        if app.on_exit_callback:
            func = app.on_exit_callback[0]
            if len(app.on_exit_callback) > 1:
                args = (app, *app.on_exit_callback[1:])
            else:
                args = (app,)
            await func(*args) if iscoroutinefunction(func) else func(*args)

        if not known:
            if exc_type or exc_value or traceback:
                await plog.b_red(app.__class__.__name__, "\nException occured in %s.\nLine: %s.\nfunc: %s.\nCode Part: `%s`.\nexc_type: %s.\ntext: %s.\n" % (*extract_tb(traceback)[-1], str(exc_type), exc_value))

        if exc_value and isinstance(exc_value, BlazeioException): return False

        if not isinstance(exc_value, CancelledError):
            if app.close_on_exit == False: return False

        if (protocol := getattr(app, "protocol", None)):
            if isinstance(protocol, BlazeioClientProtocol):
                protocol.cancel()
            else:
                await protocol.__close__()
                await protocol.__wait_closed__.wait()

        return False

    def conn(app, *args, **kwargs): return app.prepare(*args, **kwargs)

    async def prepare(app, *args, clean: bool = False, **kwargs):
        if app.close_on_exit != False:
            app.close_on_exit = False

        if app.protocol and app.has_sent_headers and not app.is_prepared() and not app.protocol.transport.is_closing(): return app

        if not args and not kwargs:
            args, kwargs = app.args, app.kwargs
        else:
            app.args, app.kwargs = args, kwargs

        return await app.create_connection(*args, **kwargs)

    def form_urlencode(app, form: dict):
        return "&".join(["%s=%s" % (key, app.url_encode_sync(str(form[key]))) for key in form]).encode()

    async def create_connection(app, url: (str, None) = None, method: (str, None) = "get", headers: dict = {}, connect_only: bool = False, host: (int, None) = None, port: (int, None) = None, path: (str, None) = None, content: (tuple[bool, AsyncIterable[bytes | bytearray]] | None) = None, proxy: (tuple,dict) = {}, add_host: bool = True, timeout: float = 30.0, json: dict = {}, cookies: dict = {}, response_headers: dict = {}, params: dict = {}, body: (bool, bytes, bytearray) = None, stream_file: (None, tuple) = None, decode_resp: bool = True, encode_writes: bool = True, max_unthreaded_json_loads_size: int = 102400, follow_redirects: bool = False, auto_set_cookies: bool = False, status_code: int = 0, form_urlencoded: (None, dict) = None, multipart: (None, dict) = None, encoder: any = None, default_writer: any = None, eof_sent: bool = False, has_sent_headers: bool = False, decompressor: any = None, compressor: any = None, send_headers: bool = True, prepare_http: bool = True, **kwargs):
        __locals__ = locals()
        for key in app.__slots__:
            if (val := __locals__.get(key, NotImplemented)) == NotImplemented: continue
            if isinstance(val, dict): val = dict(val)
            elif isinstance(val, list): val = list(val)
            setattr(app, key, val)

        stdheaders = dict(headers)
        
        if app.protocol:
            app.reset_protocol()
            proxy = None

        if method:
            method = method.upper()

        if not host and not port:
            if params:
                params = {i: app.url_encode_sync(str(params[i])) for i in params}

            app.host, app.port, app.path = ioConf.url_to_host(url, params)

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
            client_protocol = BlazeioClient

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
            body = dumps(json, indent=0).encode()
            normalized_headers["Content-type"] = "application/json"

        if body:
            normalized_headers["Content-length"] = str(len(body))

        if (content is not None or body is not None) and not "Content-length" in normalized_headers and not "Transfer-encoding" in normalized_headers and method not in {"GET", "HEAD", "OPTIONS", "CONNECT", "DELETE"}:
            if not isinstance(content, (bytes, bytearray)):
                normalized_headers["Transfer-encoding"] = "chunked"
            else:
                normalized_headers["Content-length"] = str(len(content))

        if app.port == 443:
            ssl = kwargs.pop("ssl", get_ssl_context())
        else:
            ssl = kwargs.pop("ssl", None)

        if "Content-length" in normalized_headers and normalized_headers.get(i := "Transfer-encoding"):
            normalized_headers.pop(i)

        remote_host, remote_port = app.proxy_host or app.host, app.proxy_port or app.port

        if not app.protocol:
            if client_protocol != BlazeioClient:
                transport, app.protocol = await app.loop.create_connection(lambda: client_protocol(evloop=app.loop, **kwargs), host = remote_host, port = remote_port, ssl = ssl, **{i: kwargs[i] for i in kwargs if i not in client_protocol.__slots__ and i not in app.__slots__})
            else:
                app.protocol = client_protocol(remote_host, remote_port, ssl = ssl, **kwargs)

                await app.protocol.create_connection()

                if app.protocol.proxy and ssl and not app.protocol.proxy.tls_started:
                    await app.protocol.proxy.start_tls()

            if connect_only: return app

        payload = ioConf.gen_payload(method, stdheaders, app.path, str(app.port))

        if body: payload += body

        if send_headers:
            await app.protocol.push(payload)
            app.has_sent_headers = True
        
        app.configure_writer(normalized_headers)

        if app.encode_writes and (encoding := normalized_headers.get("Content-encoding", None)) and (encoder := getattr(app, "%s_encoder" % encoding, NotImplemented)) is not NotImplemented:
            app.encoder = encoder

        if content is not None:
            if isinstance(content, (bytes, bytearray)):
                await app.write(content)
            elif isinstance(content, AsyncIterable):
                async for chunk in content: await app.write(chunk)
                await app.eof()
            else:
                raise Err("content must be AsyncIterable | bytes | bytearray")

            if prepare_http:
                await app.prepare_http()

        elif (method in app.NON_BODIED_HTTP_METHODS) or body:
            if prepare_http:
                await app.prepare_http()

        if app.is_prepared() and (callbacks := kwargs.get("callbacks")):
            for callback in callbacks: await callback(app) if iscoroutinefunction(callback) else callback(app)

        return app

    def configure_writer(app, normalized_headers):
        if not app.default_writer:
            if "Transfer-encoding" in normalized_headers: app.default_writer = app.write_chunked
            else:
                app.default_writer = app.protocol.push

    async def proxy_config(app, headers, proxy):
        username, password = None, None
        if isinstance(proxy, dict):
            if not (proxy_host := proxy.get("host")) or not (proxy_port := proxy.get("port")):
                raise Err("Proxy dict must have `host` and `port`.")

            app.proxy_host, app.proxy_port = proxy_host, proxy_port

            if (username := proxy.get("username")) and (password := proxy.get("password")):
                ...

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
        exception = (None, None, None)
        _yielded = 0
        try:
            app = app(*(args[0], method, *args[1:]), **kwargs)
            _yield = await app.__aenter__()
            _yielded = 1
            yield _yield
        except Exception as e:
            exception = (type(e).__name__, e, e.__traceback__)
        finally:
            await app.__aexit__(*exception)
            if exception[1]: raise exception[1]

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
            raise Eof("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

class __Request__(metaclass=DynamicRequestResponse):
    def __init__(app): pass

    @classmethod
    async def requestify(app, response_type: str, args, kwargs):
        async with Session(*args, **kwargs) as instance:
            return await getattr(instance, response_type)()

Session.request = __Request__

class __SessionPool__:
    __slots__ = ("sessions", "loop", "max_conns", "max_contexts", "log", "timeout", "max_instances", "should_ensure_connected")
    def __init__(app, evloop = None, max_conns = 0, max_contexts = 2, keepalive = False, keepalive_interval: int = 30, log: bool = False, timeout: int = 60, max_instances: int = 100, should_ensure_connected: bool = True):
        app.sessions, app.loop, app.max_conns, app.max_contexts, app.log, app.timeout, app.max_instances, app.should_ensure_connected = {}, evloop or ioConf.loop, max_conns, max_contexts, log, timeout, max_instances, should_ensure_connected

    async def release(app, session=None, instance=None):
        async with instance.context:
            instance.acquires -= 1
            instance.available.set()
            instance.perf_counter = perf_counter()
            instance.context.notify(1)
    
    def is_timed_out(app, instance):
        return (perf_counter() - instance.perf_counter) >= app.timeout

    def clean_instance(app, instance):
        if instance.available.is_set() and instance.acquires < 1 and app.is_timed_out(instance):
            ...
        else:
            instance.clean_cb = ReMonitor.add_callback(app.timeout, app.clean_instance, instance)
            return

        app.sessions.get(instance.key).remove(instance)
        if not app.sessions.get(instance.key): app.sessions.pop(instance.key)

        instance.available.clear()
        instance.session.transport.close()

    def create_instance(app, key, *args, **kwargs):
        instance = ddict(
            acquires = 0,
            key = key,
            available = SharpEvent(),
            context = ioCondition(),
            perf_counter = perf_counter()
        )
        
        instance.session = Session(*args, on_exit_callback = (app.release, instance), **kwargs)
        instance.session.close_on_exit = False
        instance.clean_cb = ReMonitor.add_callback(app.timeout, app.clean_instance, instance)

        return instance

    def get_instance(app, instances):
        for instance in instances:
            if instance.available.is_set():
                if (not app.max_contexts) and instance.context.waiter_count >= 1: continue
                instance.acquires += 1
                instance.available.clear()
                return instance

    async def get(app, url, method, *args, **kwargs):
        host, port, path = ioConf.url_to_host(url, {})
        
        if not (instances := app.sessions.get(key := (host, port))):
            app.sessions[key] = (instances := [])
            instances.append(instance := app.create_instance(key, url, method, *args, **kwargs))
        else:
            if not (instance := app.get_instance(instances)):
                if (not app.max_contexts) or (len(instances) < app.max_contexts):
                    instances.append(instance := app.create_instance(key, url, method, *args, **kwargs))
                else:
                    waiters = [i.context.waiter_count for i in instances]
                    instance = instances[waiters.index(min(waiters))]

        async with instance.context:
            await instance.context.wait()

        return instance.session

class SessionPool:
    __slots__ = ("pool", "args", "kwargs", "session", "max_conns", "connection_made_callback", "pool_memory", "max_contexts",)
    def __init__(app, *args, max_conns = 0, max_contexts = 0, connection_made_callback = None, pool_memory = None, **kwargs):
        app.max_conns, app.max_contexts, app.connection_made_callback, app.pool_memory = max_conns, max_contexts, connection_made_callback, pool_memory
        app.session, app.pool = None, None
        app.pool, app.args, app.kwargs = app.get_pool(**kwargs), args, kwargs

    def get_pool(app, **kwargs):
        if (pool_memory := app.pool_memory) is None and (pool_memory := __memory__.get("SessionPool", None)) is None:
            __memory__["SessionPool"] = (pool_memory := {})

        if not (pool := pool_memory.get("pool")):
            pool_memory["pool"] = (pool := __SessionPool__(max_conns=app.max_conns, max_contexts=app.max_contexts, **kwargs))

        return pool

    def __getattr__(app, key):
        if app.pool: return getattr(app.pool, key, None)

        elif (val := getattr(Session, key, None)): return val

        raise Eof("'%s' object has no attribute '%s'" % (app.__class__.__name__, key))

    async def __aenter__(app):
        app.session = await app.pool.get(*app.args, **app.kwargs)

        if app.connection_made_callback: app.connection_made_callback()

        await app.session.__aenter__(create_connection = False)

        return await app.session.prepare(*app.args, **app.kwargs)

        return Sessionproxy(app)

    async def __aexit__(app, *args):
        if app.session:
            return await app.session.__aexit__(*args)
        return False

    def __await__(app):
        _app = yield from app.__aenter__().__await__()
        return _app

class PooledSession:
    __slots__ = ("_super",)
    HTTP_METHODS = (
        "GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH", "TRACE", "CONNECT"
    )
    HTTP_METHODS = (*HTTP_METHODS, *(arg.lower() for arg in HTTP_METHODS))

    def __init__(app, _super):
        app._super = _super
        app()

    def __getattr__(app, key):
        if key in app.HTTP_METHODS:
            @asynccontextmanager
            async def dynamic_method(*args, **kwargs):
                async with app.method_setter(key, *args, **kwargs) as instance:
                    yield instance
        else:
            dynamic_method = None

        if dynamic_method:
            return dynamic_method
        else:
            return getattr(app._super, key)

    def __call__(app, *args, **kwargs):
        app._super.pool = SessionPool(*args, max_conns = app._super.max_conns, max_contexts = app._super.max_contexts, pool_memory = app._super.pool_memory,  **kwargs)
        return app._super.pool

    @asynccontextmanager
    async def method_setter(app, method: str, *args, **kwargs):
        exception = (None, None, None)
        _yielded = 0
        try:
            instance = app(*(args[0], method, *args[1:]), **kwargs)
            _yield = await instance.__aenter__()
            _yielded = 1
            yield _yield
        except Exception as e:
            exception = (type(e).__name__, e, e.__traceback__)
        finally:
            await instance.__aexit__(*exception)
            if exception[1]: raise exception[1]

class createSessionPool:
    __slots__ = ("pool", "pool_memory", "max_conns", "max_contexts", "Session", "SessionPool", "kwargs",)
    def __init__(app, max_conns: int = 0, max_contexts: int = 2, **kwargs):
        app.pool_memory, app.max_conns, app.max_contexts, app.pool, app.kwargs = {}, max_conns, max_contexts, None, kwargs
        app.Session = PooledSession(app)
        app.SessionPool = app.Session

    def __getattr__(app, key):
        if app.pool and hasattr(app.pool, key): return getattr(app.pool, key)
        elif (val := app.kwargs.get(key)): return val

        raise Eof("'%s' object has no attribute '%s'" % (app.__class__.__name__, key))

class _FetchAPI:
    __slots__ = ("session",)
    def __init__(app, session):
        app.session = session
    
    def __getattr__(app, method: str):
        async def fetch_api(url, *args, **kwargs):
            async with app.session(url, method, *args, **kwargs) as instance:
                return await instance.data()

        return fetch_api

class get_Session:
    __slots__ = ()
    dynamic_methods = ddict(fetch = _FetchAPI)
    def __init__(app):
        ...

    def pool(app):
        if not (pool := InternalScope.get("__get_Session_pool__")):
            if (socket_limits := InternalScope.get("socket_limits")):
                socket_limits = int(socket_limits/2)
            else:
                socket_limits = 0

            InternalScope.__get_Session_pool__ = (pool := createSessionPool(socket_limits, socket_limits))

        return pool

    def set_pool(app, pool):
        InternalScope.__get_Session_pool__ = pool
        return pool

    def __getattr__(app, key):
        if (value := app.dynamic_methods.get(key)): return value(app)

        return getattr(app.pool().Session, key)

    def __call__(app, *args, **kwargs):
        return app.pool().Session(*args, **kwargs)

    def instance(app):
        return app.pool().pool.pool

getSession = get_Session()
KeepaliveSession = getSession

if __name__ == "__main__": ...