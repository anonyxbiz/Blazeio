# Blazeio/__init__.py
from .Dependencies import *
from .Modules.streaming import *
from .Modules.server_tools import *
from .Modules.request import *
from .Modules.reasons import *
from .Client import *


class StatelessTools:
    __slots__ = ()
    __non_bodied_http_methods__: tuple = ("GET", "HEAD", "OPTIONS")
    
    # Gets passed the app: request object and calculates the timeout without instantiating a class
    @classmethod
    async def validate_timeout(cls, app, timeout: float = 5.0):
        if app.content_length is None:
            if app.headers is not None: app.content_length = int(app.headers.get("Content-Length", 0))

        if app.current_length >= app.content_length: return False

        if perf_counter() - app.__perf_counter__ >= timeout:
            if app.current_length >= app.content_length:
                raise Err("Connection Timed-Out due to inactivity")

        return True

class BlazeioPayloadUtils:
    __slots__ = ()
    def __init__(app):
        pass

    async def set_cookie(app, name: str, value: str, expires: str = "Tue, 07 Jan 2030 01:48:07 GMT", secure = False):
        if secure: secure = "; Secure"

        app.__cookie__ = "%s=%s; Expires=%s; HttpOnly%s; Path=/" % (name, value, expires, secure)

    async def pull(app, timeout: float = 600.0):
        async for chunk in app.request():
            if chunk:
                app.current_length += len(chunk)
                yield chunk
            else:
                if not await StatelessTools.validate_timeout(app, timeout): break

    async def request(app):
        while True:
            if app.__stream__:
                if app.transport.is_reading(): app.transport.pause_reading()

                yield app.__stream__.popleft()
            else:
                if app.__exploited__: break
                if not app.transport.is_reading(): app.transport.resume_reading()
                else:
                    yield None
            
            await sleep(0)

    async def buffer_overflow_manager(app):
        if not app.__is_buffer_over_high_watermark__: return

        while app.__is_buffer_over_high_watermark__:
            await sleep(0)
            if not app.__is_alive__:
                return

    async def prepare(app, headers: dict = {}, status: int = 206, reason = None, protocol: str = "HTTP/1.1"):
        if not app.__is_prepared__:
            if not reason:
                reason = StatusReason.reasons.get(status, "Unknown")

            await app.write(b"%s %s %s\r\nServer: Blazeio\r\n" % (protocol.encode(), str(status).encode(), reason.encode()))

            if app.__cookie__:
                await app.write(b"Set-Cookie: %s\r\n" % app.__cookie__.encode())
            
            app.__is_prepared__ = True
            app.__status__ = status

        if headers:
            for key, val in headers.items():
                await app.write(
                    b"%s: %s\r\n" % (key.encode(), val.encode())
                )

        await app.write(b"\r\n")

    async def transporter(app):
        # await sleep(0)
        app.__perf_counter__ = perf_counter()

        await app.on_client_connected(app)

        await app.close()
        
        await Log.debug(app, f"Completed with status {app.__status__} in {perf_counter() - app.__perf_counter__:.4f} seconds")

    async def control(app, duration=0):
        await sleep(duration)

    async def write(app, data: (bytes, bytearray)):
        await app.buffer_overflow_manager()
        
        if app.__is_alive__:
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

    async def close(app):
        app.transport.close()

class BlazeioPayload(asyncProtocol, BlazeioPayloadUtils):
    __slots__ = (
        'on_client_connected',
        '__stream__',
        '__is_buffer_over_high_watermark__',
        '__exploited__',
        '__is_alive__',
        'transport',
        'method',
        'tail',
        'path',
        'headers',
        '__is_prepared__',
        '__status__',
        'content_length',
        'current_length',
        '__perf_counter__',
        'ip_host',
        'ip_port',
        'identifier',
        '__cookie__',
        '__miscellaneous__',
        '__timeout__',
    )

    def __init__(app, on_client_connected):
        app.on_client_connected = on_client_connected
        app.__stream__ = deque()
        app.__is_buffer_over_high_watermark__ = False
        app.__exploited__ = False
        app.__is_alive__ = True
        app.method = None
        app.tail = "handle_all_middleware"
        app.path = "handle_all_middleware"
        app.headers = None
        app.__is_prepared__ = False
        app.__status__ = 0
        app.content_length = None
        app.current_length = 0
        app.__cookie__ = None
        app.__miscellaneous__ = None
        app.__timeout__ = None

        BlazeioPayloadUtils.__init__(app)

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
        app.ip_host, app.ip_port = app.transport.get_extra_info('peername')

        loop.create_task(app.transporter())

    def data_received(app, chunk):
        app.__stream__.append(chunk)

    def connection_lost(app, exc):
        app.__is_alive__ = False

    def eof_received(app):
        app.__exploited__ = True

    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False

class Handler:
    __main_handler__ = None
    def __init__(app):
        pass

    # Called on app start
    async def configure_runtime(app):
        app.before_middleware = app.declared_routes.get("before_middleware")

        app.after_middleware = app.declared_routes.get("after_middleware")

        app.handle_all_middleware = app.declared_routes.get("handle_all_middleware")
        
        if not app.before_middleware and not app.after_middleware: app.__main_handler__ = app.serve_route_no_middleware
        else:
            app.__main_handler__ = app.serve_route_with_middleware

    async def serve_route_with_middleware(app, r):
        if app.before_middleware:
            if (resp := await app.before_middleware.get("func")(r)) is not None: return resp

        await Request.prepare_http_request(r, app)

        await Log.info(r,
            "=> %s@ %s" % (
                r.method,
                r.path
            )
        )

        if route := app.declared_routes.get(r.path):
            await route.get("func")(r)

        elif handle_all_middleware := app.declared_routes.get("handle_all_middleware"):
            await handle_all_middleware.get("func")(r)
        else:
            # return
            raise Abort("Not Found", 404)

        if after_middleware := app.declared_routes.get("after_middleware"):
            await after_middleware.get("func")(r)

    async def serve_route_no_middleware(app, r):
        await Request.prepare_http_request(r, app)
        await Log.info(r,
            "=> %s@ %s" % (
                r.method,
                r.path
            )
        )

        if route := app.declared_routes.get(r.path): await route.get("func")(r)

        elif app.handle_all_middleware: await app.handle_all_middleware.get("func")(r)
        else: raise Abort("Not Found", 404)

    async def handle_client(app, r):
        try:
            app.REQUEST_COUNT += 1
            r.identifier = app.REQUEST_COUNT
            await app.__main_handler__(r)
        except Abort as e:
            await e.text(r, *e.args)
        except (Err, ServerGotInTrouble) as e: await Log.warning(r, e.message)
        except (ConnectionResetError, BrokenPipeError, CancelledError, Exception) as e:
            await Log.critical(r, e)

class OOP_RouteDef:
    def __init__(app):
        pass

    def attach(app, class_):
        for method in dir(class_):
            try:
                method = getattr(class_, method)
                if not isinstance(method, (Callable,)):
                    raise ValueError()

                if not (name := str(method.__name__)).startswith("_") or name.startswith("__"):
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
                print(e)

    def instantiate(app, to_instantiate: Callable):
        app.attach(to_instantiate)

        return to_instantiate

class SrvConfig:
    HOST, PORT = "0.0.0.0", "80"
    __timeout__ = float(60*10)
    __timeout_check_freq__ = 5
    def __init__(app): pass

class Timeout:
    def __init__(app):
        app.event_loop.create_task(app.task())
    
    async def task(app):
        while True:
            await sleep(app.ServerConfig.__timeout_check_freq__)
            await app.check()

    async def cancel(app, Payload, task, msg: str):
        try:
            task.cancel()
            await task
        except CancelledError: pass
        except Exception as e: await Log.critical("Blazeio", str(e))
        
        await Log.warning(Payload, msg)

    async def enforce_timeout(app, task):
        coro = task.get_coro()
        if not hasattr(coro, "cr_frame"): return

        if not (Payload := coro.cr_frame.f_locals.get("app")): return

        if not "<Blazeio.BlazeioPayload" in str(Payload): return

        if not hasattr(Payload, "__perf_counter__"): return

        if not Payload.__is_alive__: await app.cancel(Payload, task, "Task [%s] cancelled -- client disconnected." % (task.get_name()))

        __perf_counter__ = getattr(Payload, "__perf_counter__")

        duration = perf_counter() - __perf_counter__
        
        timeout = Payload.__timeout__ or app.ServerConfig.__timeout__

        if duration >= timeout: await app.cancel(Payload, task, "BlazeioTimeout:: Task [%s] cancelled due to Timeout exceeding the limit of (%s), task took (%s) seconds." % (task.get_name(), str(timeout), str(duration)))

    async def check(app):
        for task in all_tasks():
            if task is not current_task():
                try:
                    await app.enforce_timeout(task)
                except AttributeError as e: await Log.warning(e)
                except Exception as e: await Log.warning(e)

class App(Handler, OOP_RouteDef, Timeout):
    event_loop = loop
    REQUEST_COUNT = 0
    declared_routes = OrderedDict()
    ServerConfig = SrvConfig()

    __server_config__ = {
        "__http_request_heading_end_seperator__": b"\r\n\r\n",
        "__http_request_heading_end_seperator_len__": 4,
        "__http_request_max_buff_size__": 102400,
        "__http_request_initial_separatir__": b' ',
        "__http_request_auto_header_parsing__": True,
    }
    

    @classmethod
    async def init(app, **kwargs):
        app = app()
        for i in app.__class__.__bases__: i.__init__(app)

        for key, val in dict(kwargs).items():
            if key in app.__server_config__:
                app.__server_config__[key] = val
                kwargs.pop(key, None)
        
        if kwargs:
            app.ServerConfig.__dict__.update(**kwargs)

        return app

    @classmethod
    def init_sync(app, **kwargs):
        return loop.run_until_complete(App.init(**kwargs))

    def add_route(app, func: Callable, route_name: str = ""):
        params = {k: (\
            v.default if str(v.default) != "<class 'inspect._empty'>"\
            else None\
        ) for k, v in dict(sig(func).parameters).items()}

        if route_name == "": route_name = str(func.__name__)

        if not route_name.endswith("_middleware"):
            if (route := params.get("route")) is None:
                i, x = "_", "/"

                while (idx := route_name.find(i)) != -1:
                    timedotsleep(0)
                    route_name = route_name[:idx] + x + route_name[idx + len(i):]
            else:
                route_name = route
        
        data = {
            "func": func,
            "params": params
        }

        app.declared_routes[route_name] = data

        if route_name.startswith("/"):
            component = "route"
            color = "\033[32m"
        else:
            component = "middleware"
            color = "\033[34m"

        loop.run_until_complete(Log.info("Added %s => %s." % (component, route_name), None, color))

        return func

    def setup_ssl(app, HOST: str, PORT: int, ssl_data: dict):
        certfile, keyfile = ssl_data.get("certfile"), ssl_data.get("keyfile")
        if not certfile or not keyfile: raise Err("certfile and keyfile paths are required.")
        
        if not exists(certfile) or not exists(keyfile):
            from os import system
            system(f'openssl req -x509 -newkey rsa:2048 -keyout {keyfile} -out {certfile} -days 365 -nodes -subj "/CN={HOST}"')
        
        from ssl import create_default_context, Purpose 
        
        ssl_context = create_default_context(Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        return ssl_context
        
    async def run(app, HOST: str, PORT: int, **kwargs):
        if not (ssl_data := kwargs.get("ssl", None)):
            pass
        else:
            kwargs["ssl"] = app.setup_ssl(HOST, PORT, ssl_data)
        
        await app.configure_runtime()

        app.server = await loop.create_server(
            lambda: BlazeioPayload(app.handle_client),
            HOST,
            PORT,
            **kwargs
        )

        async with app.server:
            await Log.info("Blazeio", "Server running on %s://%s:%s" % ("http" if not ssl_data else "https", HOST, PORT))
            await app.server.serve_forever()

    async def exit(app):
        try:
            await Log.info("Blazeio", ":: KeyboardInterrupt Detected, Shutting down gracefully.")

            for task in all_tasks(loop=loop):
                if task is not current_task():
                    name = task.get_name()

                    await Log.info(
                        "Blazeio",
                        ":: [%s] Terminated" % name
                    )
 
                    try:
                        task.cancel()
                        # await task
                    except CancelledError: pass
                    except Exception as e: await Log.critical("Blazeio", e)

            await Log.info("Blazeio", ":: Event loop wiped, ready to exit.")

        except Exception as e: await Log.critical("Blazeio", str(e))
        finally:
            await Log.info("Blazeio", ":: Exited.")
            exit()

    def runner(app, HOST=None, PORT=None, **kwargs):
        HOST = HOST or app.ServerConfig.host
        PORT = PORT or app.ServerConfig.port

        try:
            if not kwargs.get("backlog"):
                kwargs["backlog"] = 5000

            if "version_control" in kwargs:
                del kwargs["version_control"]
                caller_frame = stack()[1]
                caller_file = caller_frame.filename
    
                loop.run_until_complete(VersionControlla.control(caller_file, HOST, PORT, **kwargs))
            else:
                loop.run_until_complete(app.run(HOST, PORT, **kwargs))
            
        except KeyboardInterrupt:
            loop.run_until_complete(app.exit())

if __name__ == "__main__":
    pass