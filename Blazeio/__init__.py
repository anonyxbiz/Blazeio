# Blazeio/__init__.py
from .Dependencies import *
from .Modules.streaming import *
from .Modules.server_tools import *
from .Modules.request import *
from .Client import *

class BlazeioPayloadUtils:
    __status__ = 0
    def __init__(app):
        pass

    async def pull(app, timeout: int = 30):
        if app.method in ("GET", "HEAD", "OPTIONS"): return
        timestart, timeout = perf_counter(), float(timeout)

        if not "content_length" in app.__dict__: app.content_length = int(app.headers.get("Content-Length", 0))

        if not "current_length" in app.__dict__: app.current_length = 0

        async for chunk in app.request():
            if chunk:
                timestart = perf_counter()
                app.current_length += len(chunk)
                yield chunk
            else:
                if app.current_length >= app.content_length:
                    break
                elif perf_counter() - timestart >= timeout:
                    raise Err("Connection Timed-Out due to inactivity")

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
        while app.__is_buffer_over_high_watermark__:
            await sleep(0)
            if not app.__is_alive__: raise Err("Client has disconnected.")

        if app.__is_alive__:
            return True
        else:
            raise Err("Client has disconnected.")

    async def prepare(app, headers: dict = {}, status: int = 206, reason: str = "Partial Content", protocol: str = "HTTP/1.1"):
        if not app.__is_prepared__:
            data = "%s %s %s\r\n" % (protocol, str(status), reason)
            
            await app.write(bytearray(data, "utf-8"))

            app.__is_prepared__ = True
            app.__status__ = status

        await app.write(b"Server: Blazeio\r\n")
        
        if headers:
            for key, val in headers.items():
                await app.write(
                    b"%s: %s\r\n" % (key.encode(), val.encode())
                )

            await app.write(b"\r\n")

    async def transporter(app):
        await sleep(0)
        app.__perf_counter__ = perf_counter()
    
        app.method = None
        app.tail = "handle_all_middleware"
        app.path = "handle_all_middleware"
        app.headers = None
        app.ip_host, app.ip_port = app.transport.get_extra_info('peername')

        await app.on_client_connected(app)
        
        await app.close()
        
        await Log.debug(app, " => %s@%s %s Completed in %s seconds" % (app.method, app.__status__, app.path, str(perf_counter() - app.__perf_counter__)[:6]) )

    async def control(app, duration=0):
        await sleep(duration)

    async def write(app, data: (bytes, bytearray)):
        if await app.buffer_overflow_manager():
            app.transport.write(data)

    async def close(app):
        app.transport.close()

class BlazeioPayload(asyncProtocol, BlazeioPayloadUtils):
    def __init__(app, on_client_connected):
        app.on_client_connected = on_client_connected
        app.__stream__ = deque()
        app.__is_buffer_over_high_watermark__ = False
        app.__exploited__ = False
        app.__is_alive__ = True
        app.__is_prepared__ = False

        BlazeioPayloadUtils.__init__(app)

    def connection_made(app, transport):
        transport.pause_reading()
        app.transport = transport
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

class App:
    event_loop = loop
    REQUEST_COUNT = 0
    default_methods = ["GET", "POST", "OPTIONS", "PUT", "PATCH", "HEAD", "DELETE"]
    server = None

    memory = {
        "routes": OrderedDict(),
        "max_routes_in_memory": 20
    }
    memory["routes"]["null"] = None
    quiet = False

    @classmethod
    async def init(app, **kwargs):
        app = app()
        app.__dict__.update(**kwargs)
        app.declared_routes = OrderedDict()

        return app

    @classmethod
    def init_sync(app, **kwargs):
        return loop.run_until_complete(App.init(**kwargs))

    def add_route(app, func: Callable, route_name = None):
        if not route_name:
            route_name = name = str(func.__name__)

        signature = sig(func)
        params = dict(signature.parameters)

        if (alt_route_name := params.get("route")):
            route_name = alt_route_name.default

        methods_param = params.get("methods", None)
        if methods_param:
            methods = methods_param.default
        else:
            methods = app.default_methods

        if isinstance(methods, list):
            methods = {method: True for method in methods}
        elif isinstance(methods, str):
            methods = {methods: True}

        params_ = OrderedDict()

        for k, v in params.items():
            params_[k] = v.default

        data = {
            "func": func,
            "methods": methods,
            "params": params_
        }

        if not route_name.endswith("_middleware"):
            route_name = route_name.replace("_", "/")

        app.declared_routes[route_name] = data
        return func

    async def append_class_routes(app, class_):
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
                    await Log.info("Added route => %s." % route_name)
                else:
                    await Log.info("Added Middleware => %s." % name)


                app.add_route(method, name)

            except ValueError:
                pass
            except Exception as e:
                await Log.error(e)

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
                    print("Added route => %s." % route_name)
                else:
                    print("Added Middleware => %s." % name)


                app.add_route(method, name)

            except ValueError:
                pass
            except Exception as e:
                print(e)

    async def serve_route(app, r):
        await Request.set_data(r)

        await Log.info(r,
            "=> %s@ %s" % (
                r.method,
                r.path
            )
        )

        # Handle before_middleware
        if before_middleware := app.declared_routes.get("before_middleware"):
            await before_middleware.get("func")(r)
        
        if route := app.declared_routes.get(r.path):
            await route.get("func")(r)

        elif handle_all_middleware := app.declared_routes.get("handle_all_middleware"):
            await handle_all_middleware.get("func")(r)
        else:
            raise Abort("Not Found", 404, "Not Found")

        if after_middleware := app.declared_routes.get("after_middleware"):
            await after_middleware.get("func")(r)

    async def handle_client(app, r):
        try:
            app.REQUEST_COUNT += 1
            r.identifier = app.REQUEST_COUNT
            await app.serve_route(r)
            
        except Abort as e:
            await e.text(r, *e.args, **e.kwargs)

        except (Err, ServerGotInTrouble) as e: await Log.warning(r, e.message)
        
        except (ConnectionResetError, BrokenPipeError, CancelledError, Exception) as e:
            await Log.critical(r, e)

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
            await Log.info("Blazeio", "KeyboardInterrupt Detected, Shutting down gracefully.")

            to_wait_for = []

            for task in all_tasks(loop=loop):
                if task is not current_task():
                    data = str(task)
                    name = None

                    if (spr := "name='") in data:
                        name = data.split(spr)[1].split("'")[0]
                    else:
                        name = data[:10]

                    await Log.info(
                        "Blazeio",
                        "Task %s Terminated" % name
                    )

                    task.cancel()
                    to_wait_for.append(task)

            for t in to_wait_for:
                try:
                    await t
                except CancelledError:
                    pass

            await Log.info("Blazeio", "Event loop wiped, ready to exit.")

        except Exception as e:
            await Log.error("Blazeio", e)
        finally:
            await Log.info("Blazeio", "Exited.")
            exit()

    def runner(app, HOST, PORT, **kwargs):
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