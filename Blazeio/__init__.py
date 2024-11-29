# Blazeio/__init__.py
from .Dependencies import new_event_loop, io_run, CancelledError, get_event_loop, io_start_server, dumps, loads, exit, dt, sig, Callable, Err, ServerGotInTrouble, p, Packdata, Log, current_task, all_tasks

from .Modules.safeguards import SafeGuards
from .Modules.streaming import Stream, Deliver, Abort
from .Modules.static import StaticFileHandler
from .Modules.request import Request
from .Modules.IN_MEMORY_STATIC_CACHE import IN_MEMORY_STATIC_CACHE
from .Client import Session

class App:
    event_loop = None
    REQUEST_COUNT = 0
    default_methods = ["GET", "POST", "OPTIONS", "PUT", "PATCH", "HEAD", "DELETE"]
    server = None

    @classmethod
    async def init(app, **kwargs):
        app = app()
        app.__dict__.update(kwargs)
        if app.event_loop is None:
            app.event_loop = new_event_loop()

        app.declared_routes = {}

        return app

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
        
        p("Added route => %s." % route_name)
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

                app.add_route(method, name)

            except ValueError:
                pass
            except Exception as e:
                p(e)
    
    async def serve_route(app, r, route=None):
        await Request.set_data(r)
        app.REQUEST_COUNT += 1
        r.identifier = app.REQUEST_COUNT

        await Log.m(r,
            "=> %s@ %s" % (
                r.method,
                r.path
            )
        )

        # Handle before_middleware
        if (before_middleware := app.declared_routes.get("before_middleware")):
            await before_middleware.get("func")(r)

        if r.path in app.declared_routes:
            route = app.declared_routes[r.path]

        # Handle routes
        if route:
            await route.get("func")(r)
        else:
            if (handle_all_middleware := app.declared_routes.get("handle_all_middleware")):
                await handle_all_middleware.get("func")(r)
            else:
                raise Err("Not Found")

        # Handle after_middleware
        if (after_middleware := app.declared_routes.get("after_middleware")):
            await after_middleware.get("func")(r)

    async def finalize(app, r):
        try:
            r.response.close()
            await r.response.wait_closed()
        except (
            Err,
            Abort,
            ConnectionResetError,
            BrokenPipeError,
            CancelledError,
            Exception
        ) as e:
            pass

    async def handle_client(app, reader, writer, r=None):
        try:
            r = await Packdata.add(request=reader, response=writer, handler=None)

            await app.serve_route(r)

        except ServerGotInTrouble as e:
            await Log.m(
                r,
                "ServerGotInTrouble: %s" % str(e)
            )

        except Err as e:
            await Log.m(r, e)

        except Abort as e:
            try:
                # await Log.m(r, e)
                await e.text(r)
            except (Err, Abort, Exception) as e:
                p(e)
                
        except (
            ConnectionResetError,
            BrokenPipeError,
            CancelledError,
            Exception
        ) as e:
            await Log.m(r, "Exception caught: %s" % str(e))

        finally:
            await app.finalize(r)

    async def run(app, HOST, PORT, **kwargs):
        app.server = await io_start_server(app.handle_client, HOST, PORT, **kwargs)
    
        async with app.server:
            p("Server running on http://%s:%s" % (HOST, PORT))
            await app.server.serve_forever()

    async def exit(app):
        try:
            await Log.say("Blazeio", "KeyboardInterrupt Detected, Shutting down gracefully.")
    
            to_wait_for = []
    
            for task in all_tasks(loop=app.event_loop):
                if task is not current_task():
                    data = str(task)
                    name = None
    
                    if (spr := "name='") in data:
                        name = data.split(spr)[1].split("'")[0]
                    else:
                        name = data[:10]
                        
                    await Log.say(
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
    
            await Log.say("Blazeio", "Event loop wiped, ready to exit.")

        except Exception as e:
            await Log.say("Blazeio", e)
        finally:
            await Log.say("Blazeio", "Exited.")
            exit()

    def runner(app, HOST, PORT, **kwargs):
        try:
            app.event_loop.run_until_complete(app.run(HOST, PORT, **kwargs))
        except KeyboardInterrupt:
            app.event_loop.run_until_complete(app.exit())

if __name__ == "__main__":
    app = run(Server.setup())
    HOST = "0.0.0.0"
    PORT = "8080"

    app.web.runner(HOST, PORT, backlog=5000)
