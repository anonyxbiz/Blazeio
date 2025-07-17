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
from .Modules.onrender import *
from .Other._refuture import *

class Handler:
    __main_handler__ = NotImplemented
    def __init__(app): pass

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
        if app.__main_handler__ is not NotImplemented: return

        app.before_middleware = app.declared_routes.get("before_middleware")

        app.after_middleware = app.declared_routes.get("after_middleware")

        app.handle_all_middleware = app.declared_routes.get("handle_all_middleware")
        
        if not app.before_middleware and not app.after_middleware and not app.handle_all_middleware:
            app.__main_handler__ = app.serve_route_no_middleware
        else:
            app.__main_handler__ = app.serve_route_with_middleware

    async def serve_route_with_middleware(app, r):
        await Request.prepare_http_request(r, app)

        if app.ServerConfig.__log_requests__: await app.log_request(r)

        if app.before_middleware: await app.before_middleware.get("func")(r)

        if route := app.declared_routes.get(r.path): await route.get("func")(r)

        elif handle_all_middleware := app.declared_routes.get("handle_all_middleware"):
            await handle_all_middleware.get("func")(r)

        else: raise Abort("Not Found", 404)

        if after_middleware := app.declared_routes.get("after_middleware"):
            await after_middleware.get("func")(r)

    async def serve_route_no_middleware(app, r):
        await Request.prepare_http_request(r, app)
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
            try: await e.text(r)
            except Exception as e: await app.handle_exception(r, e, Log.critical if app.ServerConfig.__log_requests__ else log.critical)
        except (Err, ServerGotInTrouble) as e: await Log.warning(r, e)
        except (ClientDisconnected, Eof, ServerDisconnected): pass
        except KeyboardInterrupt: raise
        except (ConnectionResetError, BrokenPipeError, CancelledError) as e: pass
        except Exception as e: await app.handle_exception(r, e, Log.critical if app.ServerConfig.__log_requests__ else log.critical)

        if app.ServerConfig.__log_requests__:
            await Log.debug(r, "Completed with status %s in %s seconds" % (str(r.__status__), round(perf_counter() - r.__perf_counter__, 4)))

class SrvConfig:
    def __init__(app):
        app.host: str =  "0.0.0.0"
        app.port: int = 8000
        app.__timeout__: float = float(60*10)
        app.__timeout_check_freq__: int = 30
        app.__health_check_freq__: int = 30
        app.__log_requests__: bool = False
        app.INBOUND_CHUNK_SIZE: (None, int) = None
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
    def __init__(app, func, *args, **kwargs): app.func, app.args, app.kwargs = func, args, kwargs

    def run(app): app.func(*app.args, **app.kwargs)

    async def arun(app): await app.func(*app.args, **app.kwargs)

class Middlewarez:
    __slots__ = ("web", "middlewares",)
    def __init__(app, web, middlewares={}):
        __locals__ = locals()
        for i in app.__slots__:
            if i in __locals__:
                setattr(app, i, __locals__.get(i))

    def __getattr__(app, name):
        return getattr(app.web, name)

class Add_Route:
    __slots__ = ("web", )
    methods = ("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "ALL", "ANY")
    any_methods = ("ALL", "ANY")

    def __init__(app, web):
        __locals__ = locals()
        for i in app.__slots__:
            if i in __locals__:
                setattr(app, i, __locals__.get(i))

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

class App(Handler, OOP_RouteDef):
    __server_config__ = {
        "__http_request_heading_end_seperator__": b"\r\n\r\n",
        "__http_request_heading_end_seperator_len__": 4,
        "__http_request_max_buff_size__": 102400,
        "__http_request_initial_separatir__": b' ',
        "__http_request_auto_header_parsing__": True,
        "funcname_normalizers": {
            "_": "/"
        }
    }

    @classmethod
    async def init(app, *args, **kwargs):
        return app(*args, **kwargs)

    @classmethod
    def init_sync(app, *args, **kwargs):
        return app(*args, **kwargs)

    def __init__(app, *args, evloop = loop, **kwargs):
        app.event_loop = evloop
        app.REQUEST_COUNT = 0
        app.declared_routes = OrderedDict()
        app.on_exit = deque()
        app.is_server_running = SharpEvent(False, loop)
        app._server_closing = SharpEvent(False, app.event_loop)
        app.wait_closed = SharpEvent(False, app.event_loop)
        app.ServerConfig = SrvConfig()
        app.ServerConfig.args, app.ServerConfig.kwargs = args, kwargs
        for i in app.__class__.__bases__: i.__init__(app)

        if len(args) >= 2:
            app.ServerConfig.__dict__["host"], app.ServerConfig.__dict__["port"] = args[:2]

        for key, val in dict(kwargs).items():
            if key in app.__server_config__:
                app.__server_config__[key] = val
                kwargs.pop(key, None)
        
        if kwargs:
            app.ServerConfig.__dict__.update(**kwargs)

        ReMonitor.add_server(app)

    def __getattr__(app, name):
        if name == "route":
            app.route = Add_Route(app)
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
    
            loop.create_task(Log.info("Added %s => %s." % (component, route_name), None, color, func = app.add_route))
    
            return func
    
    def route_validator(app):
        for route_name in app.declared_routes:
            if isinstance(route := app.declared_routes[route_name], Multirouter):
                app.declared_routes[route_name] = route.get_router()

    def setup_ssl(app, HOST: str, PORT: (int, None) = None, ssl_data: dict = {}, setup = True):
        certfile, keyfile = ssl_data.get("certfile"), ssl_data.get("keyfile")
        if not certfile or not keyfile: 
            raise Err("certfile and keyfile paths are required.")

        if not path.exists(certfile) or not path.exists(keyfile):
            proc = sb_run('openssl req -x509 -newkey rsa:2048 -keyout %s -out %s -days 365 -nodes -subj "/CN=%s"' % (keyfile, certfile, HOST), shell=True, stdout=PIPE, stderr=PIPE, text=True)

            ioConf.loop.create_task(plog.debug("setup_ssl", "".join([chunk for chunk in proc.stdout])))

            if proc.stderr:
                ioConf.loop.create_task(plog.critical("setup_ssl", "".join([chunk for chunk in proc.stderr])))

        if not setup: return

        ssl_context = create_default_context(Purpose.CLIENT_AUTH)

        ssl_context.options |= OP_NO_COMPRESSION
        ssl_context.post_handshake_auth = False

        ssl_context.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')
        ssl_context.verify_mode = CERT_NONE
        
        try:
            ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        except SSLError as e:
            raise Err(f"SSL certificate loading failed: {str(e)}")

        ssl_context.set_ecdh_curve('prime256v1')
        
        return ssl_context

    def bind_to_proxy(app, *args, **kwargs):
        return app.ServerConfig.schedule_coro(app.add_to_proxy(*args, **kwargs))

    def on_exit_middleware(app, *args, **kwargs): app.on_exit.append(OnExit(*args, **kwargs))

    def sock(app, *args, **kwargs):
        if not (sock := app.ServerConfig.sock):
            app.ServerConfig.sock = (sock := socket(AF_INET, SOCK_STREAM, *args, **kwargs))
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

        return sock

    def runner(app, host: (None, str) = None, port: (None, int) = None, **kwargs):
        try:
            app.event_loop.run_until_complete(app.run(host, port, **kwargs))
        except (KeyboardInterrupt, Exception) as e:
            app.event_loop.run_until_complete(app.exit(e))
        finally:
            return app

    def get_server(app):
        if not app.ServerConfig.server_context:
            app.ServerConfig.set_server_context(lambda protocol, *args, **kwargs: app.event_loop.create_server(lambda: protocol(app.handle_client, app.event_loop, ioConf.INBOUND_CHUNK_SIZE), *args, **kwargs))

        return app.ServerConfig.server_context

    def reboot(app):
        ReMonitor.reboot()
        app.__init__(*app.ServerConfig.args, **app.ServerConfig.kwargs)

    async def add_to_proxy(app, *args, **kwargs):
        from .Other.multiplexed_proxy import scope
        state = await scope.whclient.add_to_proxy(args[0], app.ServerConfig.port, *args[1:], **kwargs)
        app.ServerConfig.server_address = state.get("server_address")
        return state

    async def run(app, host: (None, str) = None, port: (None, int) = None, **kwargs):
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

        async with app.server:
            app.event_loop.create_task(Log.magenta("Blazeio [PID: %s]" % pid, " Server running on %s, Request Logging is %s.\n" % (app.ServerConfig.server_address, "enabled" if app.ServerConfig.__log_requests__ else "disabled"), func = app.run))
            await app.server.start_serving()
            app.is_server_running.set()
            await app._server_closing.wait()

            app.wait_closed.set()

    async def cancelloop(app, loop):
        cancelled_tasks = []
        for task in (tasks := all_tasks(loop=loop)):
            if task is not current_task():
                cancelled_tasks.append(task)
                task.cancel()

        for task in cancelled_tasks:
            async with Ehandler(ignore = CancelledError):
                await task
            await Log.warning(":: %s" % "Task [%s] Cancelled" % task.get_name())
            cancelled_tasks.remove(task)

    async def exit(app, e = None, exception_handled = False, terminate = NotImplemented):
        if not exception_handled:
            await app.is_server_running.wait()
            if e and isinstance(e, KeyboardInterrupt):
                if terminate is NotImplemented:
                    terminate = True

            try: await app.exit(e, True, terminate)
            except Exception as e: await traceback_logger(e, str(e))
            except KeyboardInterrupt: terminate = True
            finally:
                await Log.b_red(":: %s" % "Exited.")
                await log.flush()

                if (terminate is NotImplemented or not terminate):
                    return None
                return main_process.terminate()

        if isinstance(e, KeyboardInterrupt):
            await Log.warning(":: %s" % "KeyboardInterrupt Detected.")

        elif isinstance(e, Exception):
            await traceback_logger(e)
        
        await Log.warning(":: %s" % "Shutting down gracefully.")

        app.server.close()
        app._server_closing.set()
        await app.wait_closed.wait()
        await app.cancelloop(app.event_loop)

        for callback in app.on_exit:
            if iscoroutinefunction(callback.func):
                await callback.arun()
            else:
                callback.run()

            await Log.warning(":: %s" % "Executed app.on_exit `callback`: %s." % callback.func.__name__)

        await Log.warning(":: %s" % "Event loop wiped, ready to exit.")

if __name__ == "__main__":
    pass