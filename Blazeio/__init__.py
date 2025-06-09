# Blazeio/__init__.py
from .Dependencies import *
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
        tb = extract_tb(e.__traceback__)
        filename, lineno, func, text = tb[-1]
        
        msg = "\nException occured in %s.\nLine: %s.\nCode Part: `%s`.\nfunc: %s.\ntext: %s.\n" % (filename, lineno, text, func, str(e))

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
            try: await e.text()
            except Exception as e: await app.handle_exception(r, e, Log.critical if app.ServerConfig.__log_requests__ else log.critical)
        except (Err, ServerGotInTrouble) as e: await Log.warning(r, e)
        except (ClientDisconnected, Eof, ServerDisconnected): pass
        except KeyboardInterrupt: raise
        except (ConnectionResetError, BrokenPipeError, CancelledError) as e: pass
        except Exception as e: await app.handle_exception(r, e, Log.critical if app.ServerConfig.__log_requests__ else log.critical)

        if app.ServerConfig.__log_requests__:
            await Log.debug(r, "Completed with status %s in %s seconds" % (str(r.__status__), round(perf_counter() - r.__perf_counter__, 4)))

class OOP_RouteDef:
    def __init__(app):
        pass

    def attach(app, class_):
        for method in dir(class_):
            try:
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

                app.add_route(method, name)

            except ValueError:
                pass
            except Exception as e:
                pass

    def instantiate(app, to_instantiate: Callable):
        app.attach(to_instantiate)

        return to_instantiate

class SrvConfig:
    HOST: str =  "0.0.0.0"
    PORT: int = 8000
    __timeout__: float = float(60*10)
    __timeout_check_freq__: int = 30
    __health_check_freq__: int = 30
    __log_requests__: bool = False
    INBOUND_CHUNK_SIZE: (None, int) = None
    server_protocol = BlazeioServerProtocol

    def __init__(app): pass

class OnExit:
    __slots__ = ("func", "args", "kwargs")
    def __init__(app, func, *args, **kwargs): app.func, app.args, app.kwargs = func, args, kwargs

    def run(app): app.func(*app.args, **app.kwargs)

class Middlewarez:
    __slots__ = ("web", "middlewares",)
    def __init__(app, web, middlewares={}):
        __locals__ = locals()
        for i in app.__slots__:
            if i in __locals__:
                setattr(app, i, __locals__.get(i))

    def __getattr__(app, name):
        func = getattr(app.web, name)
        return func

class Add_Route:
    __slots__ = ("web", "middlewarez",)
    methods = ("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "ALL",)

    def __init__(app, web):
        __locals__ = locals()
        for i in app.__slots__:
            if i in __locals__:
                setattr(app, i, __locals__.get(i))

        app.middlewarez = Middlewarez(app)

    def __getattr__(app, name):
        if not name.upper() in app.methods:
            raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

        def method_route(*args, **kwargs):
            return app.add_route(*args, **kwargs, method=name.upper())

        return method_route

    def add_route(app, path: str = "", method: str = ""):
        async def before_func(r):
            if method != "ALL" and r.method != method:
                raise Abort("Method not allowed", 405)
            
            if app.middlewarez.middlewares.get(method):
                for middleware in app.middlewarez.middlewares.get(method):
                    await middleware["func"](r)

        def decor(func: Callable):
            async def wrapped_func(r, *args, **kwargs):
                if path: await before_func(r)
                return await func(r, *args, **kwargs)

            if path: app.web.add_route(wrapped_func, path)
            else:
                if method == "ALL":
                    for i in app.methods:
                        if not app.middlewarez.middlewares.get(i): app.middlewarez.middlewares[i] = []
                        app.middlewarez.middlewares[i].append({"func": wrapped_func, "method": method})
                else:
                    if not app.middlewarez.middlewares.get(method): app.middlewarez.middlewares[method] = []

                    app.middlewarez.middlewares[method].append({"func": wrapped_func, "method": method})

            return wrapped_func

        return decor

class App(Handler, OOP_RouteDef):
    event_loop = loop
    REQUEST_COUNT = 0
    declared_routes = OrderedDict()
    
    ioConf.ServerConfig = SrvConfig()
    ServerConfig = ioConf.ServerConfig
    on_exit = deque()
    is_server_running = SharpEvent(False, loop)

    __server_config__ = {
        "__http_request_heading_end_seperator__": b"\r\n\r\n",
        "__http_request_heading_end_seperator_len__": 4,
        "__http_request_max_buff_size__": 102400,
        "__http_request_initial_separatir__": b' ',
        "__http_request_auto_header_parsing__": True,
    }

    def __init__(app, *args, **kwargs):
        for i in app.__class__.__bases__: i.__init__(app)
        
        if len(args) >= 2:
            app.ServerConfig.__dict__["host"], app.ServerConfig.__dict__["port"] = args[:2]

        for key, val in dict(kwargs).items():
            if key in app.__server_config__:
                app.__server_config__[key] = val
                kwargs.pop(key, None)
        
        if kwargs:
            app.ServerConfig.__dict__.update(**kwargs)

        ReMonitor.ServerConfig = app.ServerConfig

        ReMonitor.Monitoring_thread = Thread(target=ReMonitor.Monitoring_thread_monitor, args=(app,), daemon = True)

        ReMonitor.Monitoring_thread.start()

    def __getattr__(app, name):
        if name == "route":
            app.route = Add_Route(app)
        else:
            return app.ServerConfig.__dict__.get(name)

        return getattr(app, name)

    @classmethod
    async def init(app, *args, **kwargs):
        app = app(*args, **kwargs)

        return app

    @classmethod
    def init_sync(app, *args, **kwargs):
        app = app(*args, **kwargs)
        return app

    def add_route(app, func: Callable, route_name: str = ""):
        params = {k: (\
            v.default if str(v.default) != "<class 'inspect._empty'>"\
            else None\
        ) for k, v in dict(sig(func).parameters).items()}

        if not route_name: route_name = str(func.__name__)

        if route_name == "__main_handler__":
            app.__main_handler__ = func
            return func

        if not route_name.endswith("_middleware"):
            if (route := params.get("route")) is None:
                i, x = "_", "/"
                while (idx := route_name.find(i)) != -1:
                    route_name = route_name[:idx] + x + route_name[idx + len(i):]
            else:
                route_name = route

        data = {
            "func": func,
            "params": params,
            "len": len(route_name),
        }

        app.declared_routes[route_name] = data

        if route_name.startswith("/"):
            component = "route"
            color = "\033[32m"
        else:
            component = "middleware"
            color = "\033[34m"

        loop.create_task(Log.info("Added %s => %s." % (component, route_name), None, color))

        return func

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

    async def run(app, host: (None, str) = None, port: (None, int) = None, **kwargs):
        if not host: host = app.ServerConfig.host
        if not port: port = app.ServerConfig.port

        if (ssl_data := kwargs.get("ssl", None)) and isinstance(ssl_data, dict):
            kwargs["ssl"] = app.setup_ssl(host, port, ssl_data)

        await app.configure_server_handler()

        protocol = app.ServerConfig.server_protocol
        
        if not "sock" in kwargs:
            args = (host, port)
        else:
            args = ()

        app.server = await app.event_loop.create_server(
            lambda: protocol(app.handle_client, app.event_loop, ioConf.INBOUND_CHUNK_SIZE),
            *args,
            **kwargs
        )

        async with app.server:
            app.event_loop.create_task(Log.magenta("Blazeio [PID: %s]" % pid, " Server running on %s://%s:%s, Request Logging is %s.\n" % ("http" if not ssl_data else "https", host, port, "enabled" if app.ServerConfig.__log_requests__ else "disabled")))

            app.event_loop.call_soon(app.is_server_running.set)

            await app.server.serve_forever()

    async def cancelloop(app, loop, warn = Log.warning):
        cancelled_tasks = []
        for task in (tasks := all_tasks(loop=loop)):
            if task is not current_task():
                cancelled_tasks.append(task)
                task.cancel()
                await warn("Task [%s] Cancelled" % task.get_name())

        try: await gather(*cancelled_tasks)
        except CancelledError: pass
        except Exception: raise

    async def exit(app, e, exception_handled = False, terminate = True):
        warn = lambda _log: Log.warning("<Blazeio.exit>", ":: %s" % str(_log))

        if not exception_handled:
            try: await app.exit(e, True)
            except Exception as e: await traceback_logger(e, str(e))
            finally:
                await warn("Exited.")
                await log.flush()
                return None if not terminate else main_process.terminate()

        if isinstance(e, KeyboardInterrupt):
            await warn("KeyboardInterrupt Detected, Shutting down gracefully.")
            app.server.close()

        else:
            await traceback_logger(e)

        for callback in app.on_exit:
            callback.run()
            await warn("Executed app.on_exit `callback`: %s." % callback.func.__name__)

        await app.cancelloop(app.event_loop, warn)

        await warn("Event loop wiped, ready to exit.")

    def on_exit_middleware(app, *args, **kwargs): app.on_exit.append(OnExit(*args, **kwargs))

    def runner(app, host: (None, str) = None, port: (None, int) = None, **kwargs):
        if not kwargs.get("backlog"):
            kwargs["backlog"] = 5000

        try:
            app.event_loop.run_until_complete(app.run(host, port, **kwargs))
        except (KeyboardInterrupt, Exception) as e:
            app.event_loop.run_until_complete(app.exit(e))
        finally:
            return app

if __name__ == "__main__":
    pass