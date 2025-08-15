# Blazeio/__init__.py
from .Dependencies.alts import *
from .Protocols.server_protocol import *
from .Protocols.client_protocol import *
from .Modules.streaming import *
from .Modules.server_tools import *
from .Modules.request import *
from .Modules.reasons import *
from .Client import *
from .Modules.templatify import *
from .Other._refuture import *

is_on_render = lambda: environ.get("RENDER")

class Handler:
    def __init__(app):
        app.__main_handler__ = NotImplemented
        app.__default_handler__ = NotImplemented
        app.__default_parser__ = Request.prepare_http_request

    async def log_request(app, r):
        r.__perf_counter__ = perf_counter()

        await Log.info(r,
            "=> %s@ %s" % (
                r.method,
                r.path
            )
        )
    
    def __set_main_handler__(app, func: Callable):
        app.__main_handler__ = func
        return func

    def __server_handler__(app):
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            app.__main_handler__ = func
            return wrapper

        return decorator

    async def configure_server_handler(app):
        app.before_middleware = app.declared_routes.get("before_middleware")

        app.after_middleware = app.declared_routes.get("after_middleware")

        app.handle_all_middleware = app.declared_routes.get("handle_all_middleware")

        if not app.before_middleware and not app.after_middleware and not app.handle_all_middleware:
            app.__default_handler__ = app.serve_route_no_middleware
        else:
            app.__default_handler__ = app.serve_route_with_middleware

        if app.__main_handler__ is NotImplemented:
            app.__main_handler__ = app.__default_handler__

    async def serve_route_with_middleware(app, r, prepare = True):
        if prepare: await app.__default_parser__(r, app)

        if app.ServerConfig.__log_requests__: await app.log_request(r)

        if app.before_middleware: await app.before_middleware.get("func")(r)

        if route := app.declared_routes.get(r.path): await route.get("func")(r)

        elif handle_all_middleware := app.declared_routes.get("handle_all_middleware"):
            await handle_all_middleware.get("func")(r)

        else: raise Abort("Not Found", 404)

        if after_middleware := app.declared_routes.get("after_middleware"):
            await after_middleware.get("func")(r)

    async def serve_route_no_middleware(app, r, prepare = True):
        if prepare: await app.__default_parser__(r, app)
        if app.ServerConfig.__log_requests__: await app.log_request(r)

        if route := app.declared_routes.get(r.path): await route.get("func")(r)

        else: raise Abort("Not Found", 404)
    
    async def handle_exception(app, r, e, logger, format_only=False):
        tb = e.__traceback__
        msg = "\n".join([*("Exception occured in %s.\nLine: %s.\nfunc: %s.\nCode Part: `%s`.\ntype: %s.\ntext: %s.\n" % (*extract_tb(tb)[-1], str(type(e))[8:-2], "".join([str(e)]))).split("\n")])

        if format_only: return msg

        for exc in Log.known_exceptions:
            if exc in msg: return

        if "Log" in str(logger):
            await logger(r, msg)
        else:
            await logger(msg)

    async def handle_client(app, r):
        try:
            r.ip_host, r.ip_port = r.transport.get_extra_info('peername')

            if app.ServerConfig.__log_requests__:
                r.__perf_counter__ = perf_counter()
                app.REQUEST_COUNT += 1
                r.identifier = app.REQUEST_COUNT

            await app.__main_handler__(r)

        except Abort as e:
            await e.text(r)

        except (Err, ServerGotInTrouble) as e:
            await Log.warning(r, e)
        except (ClientDisconnected, Eof, ServerDisconnected):
            ...
        except KeyboardInterrupt:
            raise
        except (ConnectionResetError, BrokenPipeError, CancelledError):
            ...
        except Exception as e:
            await app.handle_exception(r, e, Log.critical if app.ServerConfig.__log_requests__ else log.critical)

        if app.ServerConfig.__log_requests__:
            await Log.debug(r, "Completed with status %s in %s seconds" % (str(r.__status__), round(perf_counter() - r.__perf_counter__, 4)))

class SrvConfig:
    def __init__(app):
        app.host =  "0.0.0.0"
        app.port = 8000
        app.__timeout__ = float(60*10)
        app.__timeout_check_freq__ = 30
        app.__health_check_freq__ = 30
        app.__log_requests__ = False
        app.INBOUND_CHUNK_SIZE = None
        app.server_protocol = BlazeioServerProtocol
        app.sock = None
        app._pending_coros = deque()

    def __getattr__(app, name):
        return None
    
    def set_server_context(app, context):
        app.server_context = context

    def schedule_coro(app, coro):
        return app._pending_coros.append(coro)

    async def resolve_coros(app):
        while app._pending_coros:
            await app._pending_coros.popleft()

ioConf.ServerConfig = SrvConfig()

class OnExit:
    __slots__ = ("func", "args", "kwargs")
    def __init__(app, func, *args, **kwargs):
        app.func, app.args, app.kwargs = func, args, kwargs

    def run(app):
        app.func(*app.args, **app.kwargs)

    async def arun(app):
        await app.func(*app.args, **app.kwargs)

class Middlewarez:
    __slots__ = ("web", "middlewares",)
    def __init__(app, web, middlewares={}):
        app.web = web
        app.middlewares = dict(middlewares)

    def __getattr__(app, name):
        return getattr(app.web, name)

class Add_Route:
    __slots__ = ("web", )
    methods = ("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "ALL", "ANY")
    any_methods = ("ALL", "ANY")

    def __init__(app, web):
        app.web = web

    def __getattr__(app, name):
        if not name.upper() in app.methods:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

        def method_route(*args, **kwargs):
            return app.add_route(*args, **kwargs, method=name.upper())

        return method_route

    def add_route(app, path: (None, str) = None, method: (None, str) = None):
        async def before_func(r):
            if method not in app.any_methods and r.method != method:
                raise Abort("Method not allowed", 405)

        def decor(func: Callable):
            async def wrapped_func(r, *args, **kwargs):
                if path: await before_func(r)
                return await func(r, *args, **kwargs)

            app.web.add_route(wrapped_func, func, path)
            return wrapped_func

        return decor

class Routemanager(ddict):
    def normalize_funcname(app, funcname: str):
        for i, x in ioConf.default_http_server_config["funcname_normalizers"].items():
            funcname = funcname.replace(i, x)
        return funcname

    def add(app, fn, *args, **kwargs):
        app[app.normalize_funcname(fn.__name__)] = (fn, args, kwargs)
        return fn

class Deprecated:
    def __init__(app):
        ...

    @classmethod
    def init_sync(app, *args, **kwargs):
        return app(*args, **kwargs)

    @classmethod
    async def init(app, *args, **kwargs):
        return app(*args, **kwargs)

class Taskmng:
    def __init__(app):
        app.tasks = []
        app.on_exit_middleware(app.cancel_tasks)

    async def cancel_tasks(app):
        async with Ehandler(ignore = CancelledError):
            await gather(*[task for task in app.tasks if task.cancel() or True])

        app.tasks.clear()

    def create_task(app, *args, **kwargs):
        app.tasks.append(task := app.loop.create_task(*args, **kwargs))
        return task

class OOP_RouteDef:
    def __init__(app):
        ...

    def attach(app, class_):
        for method in dir(class_):
            with Ehandler(ignore = [ValueError]):
                method = getattr(class_, method)
                if not isinstance(method, (Callable,)):
                    raise ValueError()

                if (name := str(method.__name__)) == "__main_handler__":
                    app.__main_handler__ = method
                    app.create_task(plog.info("Added %s => %s." % (name, name), func = app.attach, dnewline = False, newline = False))
                    raise ValueError()

                if not name.startswith("_") or name.startswith("__"):
                    if not name.endswith("_middleware"):
                        raise ValueError()

                if not "r" in (params := dict((signature := sig(method)).parameters)):
                    raise ValueError()

                if not name.endswith("_middleware"):
                    route_name = name.replace("_", "/")

                app.add_route(method, route_name = name)

    def instantiate(app, to_instantiate: Callable):
        app.attach(to_instantiate)
        return to_instantiate

class Rproxy:
    def __init__(app):
        ...

    def bind_to_proxy(app, *args, **kwargs):
        return app.ServerConfig.schedule_coro(app.add_to_proxy(*args, **kwargs))

    async def add_to_proxy(app, *args, **kwargs):
        from .Other.multiplexed_proxy import scope
        state = await scope.whclient.add_to_proxy(args[0], app.ServerConfig.port, *args[1:], **kwargs)
        app.ServerConfig.server_address = state.get("server_address")
        return state

class Serverctx:
    def __init__(app):
        app.in_ctx = False

    def __enter__(app):
        app.in_ctx = True
        return app

    def __exit__(app, exc_t, exc_v, tb):
        app.in_ctx = False
        ioConf.run_callbacks()

class Httpkeepalive:
    def __init__(app, web, after_middleware = None, timeout: int = 60*60*5, _max: int = 1000**2):
        app.web, app.after_middleware, app.__default_handler__ = web, after_middleware, None
        app.timeout, app._max = timeout, _max

        if not app.after_middleware:
            if (after_middleware := app.web.declared_routes.pop("after_middleware", None)):
                app.after_middleware = after_middleware.get("func")

        app.configure()

    def configure(app):
        if app.web.__main_handler__ is not NotImplemented:
            app.__default_handler__ = app.web.__main_handler__

    def get_handler(app):
        return app.__default_handler__ or app.web.__default_handler__

    def prepare_keepalive(app, r):
        r += (
            b"Connection: Keep-Alive\r\n"
            b"Keep-Alive: timeout=%d, max=%d\r\n" % (app.timeout, app._max)
        )

    async def __main_handler__(app, r):
        while True:
            try:
                exc = None
                app.prepare_keepalive(r)
                await app.get_handler()(r)
                if r.headers: await r.eof()

            except (Abort, Eof, Err, ServerGotInTrouble) as e:
                if isinstance(e, Abort):
                    await e.text(r)
                else:
                    if r.headers: await r.eof()
            except Exception as e:
                exc = e
            finally:
                if app.after_middleware: await app.after_middleware(r)

                if exc: raise exc

                if r.transport.is_closing(): break

                r.utils.clear_protocol(r)

class Server:
    def __init__(app):
        ...

    def on_exit_middleware(app, *args, **kwargs): app.on_exit.append(OnExit(*args, **kwargs))

    def setup_ssl(app, host: str, port: (int, None) = None, ssl_data: dict = {}, setup = True):
        certfile, keyfile = ssl_data.get("certfile"), ssl_data.get("keyfile")
        if not certfile or not keyfile: 
            raise Err("certfile and keyfile paths are required.")

        if not path.exists(certfile) or not path.exists(keyfile):
            proc = sb_run('openssl req -x509 -newkey rsa:2048 -keyout %s -out %s -days 365 -nodes -subj "/CN=%s"' % (keyfile, certfile, host), shell=True, stdout=PIPE, stderr=PIPE, text=True)

            ioConf.loop.create_task(plog.debug("setup_ssl", "".join([chunk for chunk in proc.stdout])))

            if proc.stderr:
                ioConf.loop.create_task(plog.critical("setup_ssl", "".join([chunk for chunk in proc.stderr])))

        if not setup: return

        ssl_context = create_default_context(Purpose.CLIENT_AUTH)

        ssl_context.options |= OP_NO_COMPRESSION
        ssl_context.post_handshake_auth = False

        ssl_context.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')
        ssl_context.verify_mode = CERT_NONE
        
        with Ehandler():
            ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile)

        ssl_context.set_ecdh_curve('prime256v1')

        return ssl_context

    def sock(app, *args, **kwargs):
        if not (sock := app.ServerConfig.sock):
            app.ServerConfig.sock = (sock := socket(AF_INET, SOCK_STREAM, *args, **kwargs))
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

        return sock

    def runner(app, *args, **kwargs):
        try:
            app.event_loop.run_until_complete(app.run(*args, **kwargs))
        except (KeyboardInterrupt, Exception) as e:
            app.event_loop.run_until_complete(app.exit(e))
        finally:
            return app

    def get_server(app):
        if not app.ServerConfig.server_context:
            app.ServerConfig.set_server_context(lambda protocol, *args, **kwargs: app.event_loop.create_server(lambda: protocol(app.handle_client, app.event_loop, app.INBOUND_CHUNK_SIZE), *args, **kwargs))

        return app.ServerConfig.server_context

    def reboot(app):
        if not app.used: return
        app.__init__(*app.ServerConfig.args, **app.ServerConfig.kwargs)

    def used(app):
        return app._server_closing.is_set()
    
    def with_keepalive(app, *args, **kwargs):
        app.attach(Httpkeepalive(app, *args, **kwargs))
        sock = app.sock()
        sock.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
        sock.setsockopt(IPPROTO_TCP, TCP_KEEPIDLE, 60)
        sock.setsockopt(IPPROTO_TCP, TCP_KEEPINTVL, 60)
        sock.setsockopt(IPPROTO_TCP, TCP_KEEPCNT, 10)

    async def exit(app, e = None, exception_handled = False, terminate = NotImplemented):
        await app.wait_started()
        if e and isinstance(e, KeyboardInterrupt) and terminate is NotImplemented:
            terminate = True

        try:
            await app.shutdown(e)
        except Exception as e: await traceback_logger(e, str(e))
        except KeyboardInterrupt: terminate = True
        finally:
            if (terminate is NotImplemented or not terminate):
                return None

            return main_process.terminate()

    async def cancelloop(app, loop, except_tasks):
        async with Ehandler(ignore = (CancelledError, Eof)):
            cancelled_tasks = []
            for task in list(all_tasks(loop=app.loop)):
                if (not task in except_tasks):
                    if not app.quiet_shutdown: except_tasks.append(app.loop.create_task(plog.warning(":: Task `%s` Cancelled." % task.get_name())))
                    task.cancel()
                    cancelled_tasks.append(task)

            await gather(*cancelled_tasks)

    async def shutdown(app, e = None):
        shutdown_tasks = [current_task()]
        if isinstance(e, KeyboardInterrupt):
            shutdown_tasks.append(app.loop.create_task(plog.warning(":: %s" % "KeyboardInterrupt Detected.")))

        elif isinstance(e, Exception):
            shutdown_tasks.append(app.loop.create_task(traceback_logger(e)))

        shutdown_tasks.append(app.loop.create_task(plog.warning(":: %s" % "Shutting down gracefully.")))

        app.server.close()
        app._server_closing.set()
        await app.wait_closed.wait()

        for callback in app.on_exit:
            async with Ehandler():
                if iscoroutinefunction(callback.func):
                    shutdown_tasks.append(app.loop.create_task(callback.arun()))
                else:
                    callback.run()

            if not app.quiet_shutdown: shutdown_tasks.append(app.loop.create_task(plog.warning(":: Executed `%s` callback." % callback.func.__name__)))

        await app.cancelloop(app.event_loop, shutdown_tasks)
        await plog.b_red(":: %s" % "Event loop wiped, Exited.")

        try:
            await gather(*shutdown_tasks[1:])
        finally:
            app.exit_event.set()

    async def run(app, host: (None, str) = None, port: (None, int) = None, serve_forever = True, **kwargs):
        async with Ehandler() as e:
            app.route_validator()
            if host: app.ServerConfig.host = host
            if port: app.ServerConfig.port = port
    
            if not kwargs.get("backlog"):
                kwargs["backlog"] = 5000
    
            if app.ServerConfig.sock:
                app.ServerConfig.sock.bind((app.ServerConfig.host, app.ServerConfig.port))
                kwargs["sock"] = app.ServerConfig.sock
    
            if (ssl_data := kwargs.get("ssl", None)) and isinstance(ssl_data, dict):
                kwargs["ssl"] = app.setup_ssl(app.ServerConfig.host, app.ServerConfig.port, ssl_data)
    
            await app.configure_server_handler()
    
            protocol = app.ServerConfig.server_protocol
    
            if not "sock" in kwargs:
                args = (app.ServerConfig.host, app.ServerConfig.port)
            else:
                args = ()
    
            await app.ServerConfig.resolve_coros()

            app.server = await app.get_server()(protocol, *args, **kwargs)

            if not app.ServerConfig.server_address:
                app.ServerConfig.server_address = "%s://%s:%s" % ("http" if not ssl_data else "https", app.ServerConfig.host, app.ServerConfig.port)

                app.ServerConfig.server_addressf = app.ServerConfig.server_address + "%s"

        if e.err: return

        if serve_forever:
            await app.serve_forever()

    async def serve_forever(app):
        async with app.server:
            await app.server.start_serving()
            app.is_server_running.set()
            
            await plog.magenta("Blazeio [PID: %s]" % pid, " Server running on %s, Request Logging is %s.\n" % (app.ServerConfig.server_address, "enabled" if app.ServerConfig.__log_requests__ else "disabled"), func = app.run)

            await app._server_closing.wait()
            app.wait_closed.set()

    async def wait_started(app):
        return await app.is_server_running.wait()

class App(Handler, OOP_RouteDef, Rproxy, Server, Taskmng, Deprecated, Serverctx):
    def __init__(app, *args, **kwargs):
        app.__server_config__ = kwargs.get("__server_config__") or dict(ioConf.default_http_server_config)
        app.loop = kwargs.get("evloop") or kwargs.get("loop") or ioConf.loop
        app.REQUEST_COUNT = 0
        app.INBOUND_CHUNK_SIZE = kwargs.get("INBOUND_CHUNK_SIZE") or ioConf.INBOUND_CHUNK_SIZE
        app.declared_routes = kwargs.get("declared_routes") or OrderedDict()
        app.on_exit = kwargs.get("on_exit") or deque()
        app.quiet_shutdown = kwargs.get("quiet_shutdown", True)
        app.is_server_running = SharpEvent(evloop = app.loop)
        app._server_closing = SharpEvent(evloop = app.loop)
        app.wait_closed = SharpEvent(evloop = app.loop)
        app.exit_event = SharpEvent(evloop = app.loop)
        app.ServerConfig = SrvConfig()
        app.ServerConfig.args, app.ServerConfig.kwargs = args, kwargs

        if len(args) >= 2:
            app.ServerConfig.__dict__["host"], app.ServerConfig.__dict__["port"] = args[:2]

        for key in list(kwargs.keys()):
            if key in app.__server_config__:
                app.__server_config__[key] = kwargs.pop(key)

        if kwargs:
            app.ServerConfig.__dict__.update(**kwargs)

        ReMonitor.add_server(app)
        Super(app).__init__()

    def __getattr__(app, name):
        if name == "route":
            app.route = Add_Route(app)
        elif name == "event_loop":
            return app.loop
        else:
            return app.ServerConfig.__dict__.get(name)

        return getattr(app, name)

    def normalize_funcname(app, funcname: str):
        for i, x in app.__server_config__["funcname_normalizers"].items():
            funcname = funcname.replace(i, x)

        return funcname

    def add_route(app, func: Callable, parent_func: (None, Callable) = None, route_name: (None, str) = None):
        with Ehandler():
            if parent_func is None: parent_func = func

            params = {k: (v.default if str(v.default) != "<class 'inspect._empty'>"else None) for k, v in dict(sig(parent_func).parameters).items()}
    
            if route_name is None: route_name = str(parent_func.__name__)
    
            if route_name == "__main_handler__":
                app.__main_handler__ = func
                return func
    
            if not route_name.endswith("_middleware"):
                if (route := params.get("route")) is None:
                    route_name = app.normalize_funcname(route_name)
                else:
                    route_name = route
    
            data = {
                "func": func,
                "params": params,
                "len": len(route_name),
            }
    
            if route_name in app.declared_routes:
                if not isinstance(app.declared_routes[route_name], Multirouter):
                    app.declared_routes[route_name] = Multirouter(route_name, app.declared_routes[route_name])
                app.declared_routes[route_name].add(data)
            else:
                app.declared_routes[route_name] = data
    
            if route_name.startswith("/"):
                component = "route"
                color = "\033[32m"
            else:
                component = "middleware"
                color = "\033[34m"

            app.create_task(plog.info("Added %s => %s." % (component, route_name), func = app.add_route, dnewline = False, newline = False))
            return func

    def route_validator(app):
        for route_name in app.declared_routes:
            if isinstance(route := app.declared_routes[route_name], Multirouter):
                app.declared_routes[route_name] = route.get_router()

if __name__ == "__main__":
    pass