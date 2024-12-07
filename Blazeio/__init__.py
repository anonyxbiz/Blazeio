# Blazeio/__init__.py
from .Dependencies import io_run, CancelledError, dumps, loads, exit, dt, sig, Callable, Err, ServerGotInTrouble, p, Packdata, Log, current_task, all_tasks, loop, iopen, guess_type, asyncProtocol, sleep, perf_counter

from .Modules.safeguards import SafeGuards
from .Modules.streaming import Stream, Deliver, Abort
from .Modules.static import StaticFileHandler, Smart_Static_Server, Staticwielder
from .Modules.request import Request
from .Client import Session, Client

class Protocol(asyncProtocol):
    def __init__(app, on_client_connected):
        app.on_client_connected = on_client_connected

    def connection_made(app, transport):
        loop.create_task(app.transporter(transport))

    def data_received(app, data):
        app.r.__stream__ = data
        app.r.__received__ = True

    def connection_lost(app, exc):
        app.r.__is_alive__ = False

    def eof_received(app, *args, **kwargs):
        app.r.__exploited__ = True

    async def remove(app, count):
        await sleep(0.01)
        app.r.buffer[count] = b""

    async def read(app):
        while app.r.__is_alive__:
            if app.r.__received__:
                yield app.r.__stream__
                app.r.__received__ = False
            else:
                yield None
                await sleep(0)

    async def transporter(app, transport):
        app.r = await Packdata.add(
            __perf_counter__ = perf_counter(),
            __exploited__ = False,
            __received__ = False,
            __stream__ = b"",
            __is_alive__ = True,
            buffer = 0,
            request = app.read,
            response = transport,
            headers = {},
            method = None,
            tail = None,
            path = None,
            params = None,
            __count__ = 0,
            __retries__ = 0,
        )

        app.r.ip_host, app.r.ip_port = app.r.response.get_extra_info('peername')

        await app.on_client_connected(app.r)

        app.r.response.close()

        await Log.debug(f"Completed in {perf_counter() - app.r.__perf_counter__:.4f} seconds" )



class App:
    event_loop = loop
    REQUEST_COUNT = 0
    default_methods = ["GET", "POST", "OPTIONS", "PUT", "PATCH", "HEAD", "DELETE"]
    server = None

    memory = {
        "routes": {},
        "max_routes_in_memory": 20
    }

    @classmethod
    async def init(app, **kwargs):
        app = app()
        app.__dict__.update(kwargs)
        app.declared_routes = {}
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

        params_ = {}

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

    async def serve_route(app, r, route=None):
        await Request.set_data(r)
        await Log.info(r,
            "=> %s@ %s" % (
                r.method,
                r.path
            )
        )

        if r.path not in app.memory["routes"]:
            memory = await Packdata.add(actions=None)
            if len(app.memory["routes"]) <= app.memory.get("max_routes_in_memory") or 20:
                app.memory["routes"][r.path] = memory
        else:
            memory = app.memory["routes"][r.path]

        if not memory.actions:
            memory.actions = []

            # Handle before_middleware
            if (before_middleware := app.declared_routes.get("before_middleware")):
                memory.actions.append(before_middleware.get("func"))

                await before_middleware.get("func")(r)

            if r.path in app.declared_routes:
                route = app.declared_routes[r.path]

            # Handle routes
            if route:
                memory.actions.append(route.get("func"))

                await route.get("func")(r)

            else:
                if (handle_all_middleware := app.declared_routes.get("handle_all_middleware")):
                    memory.actions.append(handle_all_middleware.get("func"))

                    await handle_all_middleware.get("func")(r)
                else:
                    memory.actions = {
                        "raise": Abort,
                        "kwargs": {"message": "Not Found", "status": 404}
                    }

                    raise memory.actions["raise"](**memory.actions["kwargs"])

            # Handle after_middleware
            if (after_middleware := app.declared_routes.get("after_middleware")):
                memory.actions.append(after_middleware.get("func"))

                await after_middleware.get("func")(r)
        else:
            # Use memory to remember actions
            if isinstance(memory.actions, list):
                for action in memory.actions: await action(r)
            else:
                raise memory.actions["raise"](**memory.actions["kwargs"])

    async def handle_client(app, r):
        try:
            app.REQUEST_COUNT += 1
            r.identifier = app.REQUEST_COUNT
            await app.serve_route(r)

        except (Err, ServerGotInTrouble) as e: await Log.warning(r, e)
        except Abort as e: await e.text(r)
        except (ConnectionResetError, BrokenPipeError, CancelledError, Exception) as e: await Log.critical(r, e)

    async def run(app, HOST, PORT, **kwargs):
        if 1:#not "Protocol" in kwargs:
            app.server = await loop.create_server(
                lambda: Protocol(app.handle_client),
                HOST,
                PORT,
                **kwargs
            )
        else:
            app.server = await loop.create_server(
                app.handle_client,
                HOST,
                PORT,
                **kwargs
            )

        async with app.server:
            await Log.info("Blazeio", "Server running on http://%s:%s" % (HOST, PORT))
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

            loop.run_until_complete(app.run(HOST, PORT, **kwargs))
        except KeyboardInterrupt:
            loop.run_until_complete(app.exit())

if __name__ == "__main__":
    app = App.init_sync()
    HOST = "0.0.0.0"
    PORT = "8080"

    app.web.runner(HOST, PORT, backlog=5000)