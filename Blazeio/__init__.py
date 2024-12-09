# Blazeio/__init__.py
from .Dependencies import io_run, CancelledError, dumps, loads, exit, dt, sig, Callable, Err, ServerGotInTrouble, p, Packdata, Log, current_task, all_tasks, loop, iopen, guess_type, asyncProtocol, sleep, perf_counter, deque, OrderedDict, stack, create_subprocess_shell, getsize

from .Modules.streaming import Stream, Deliver, Abort
from .Modules.static import StaticFileHandler, Smart_Static_Server, Staticwielder
from .Modules.request import Request
from .Client import Session

class VersionControlla:
    @classmethod
    async def control(app, ins, HOME, HOST, PORT, **kwargs):
        async def runner():
            process = await create_subprocess_shell(
                cmd=f'python -m Blazeio --path "{HOME}" --host "{HOST}" --port "{PORT}"',
                stdout=None,
                stderr=None,
            )
            try:
                await process.wait()
            except CancelledError:
                process.terminate()
                await process.wait()
                raise

        while True:
            size = getsize(HOME)
            task = loop.create_task(runner())

            while True:
                if task.done():
                    break
                
                if getsize(HOME) == size:
                    await sleep(1)
                else:
                    await Log.warning(f"version change detected in {HOME}, reloading server...")
                    break
            
            if not task.done():
                try:
                    task.cancel()
                    await task
                except CancelledError:
                    pass

            else:
                break

class Protocol(asyncProtocol):
    def __init__(app, on_client_connected, **kwargs):
        app.__dict__.update(kwargs)
        app.on_client_connected = on_client_connected
        app.__stream__ = deque()
        app.__is_alive__ = True
        app.__exploited__ = False
        app.__is_buffer_over_high_watermark__ = False
        app.__waiting_for_write_drainage__ = None
        app.__max_buff_len__ = 10*1024
        app.transport = None

    def connection_made(app, transport):
        app.transport = transport
        loop.create_task(app.transporter())

    def data_received(app, chunk):
        app.transport.pause_reading()

        while len(chunk) >= app.__max_buff_len__:
            app.__stream__.append(chunk[:app.__max_buff_len__])
            chunk = chunk[app.__max_buff_len__:]
        
        #app.transport.pause_reading()

        app.__stream__.append(chunk)
        app.transport.resume_reading()

    def connection_lost(app, exc):
        app.__is_alive__ = False

    def eof_received(app, *args, **kwargs):
        app.__exploited__ = True
    
    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False

    async def request(app, chunk_size=None):
        
        while True:
            await sleep(0)
            
            while app.__stream__:
                yield app.__stream__.popleft()
            
            #app.transport.resume_reading()
            
            yield None

    async def write(app, data: (bytes, bytearray)):
        if app.__is_alive__:
            app.transport.write(data)
        else:
            raise Err("Client has disconnected.")

    async def close(app):
        app.transport.close()
    
    async def control(app):
        await sleep(0)

    async def transporter(app):
        await sleep(0)

        __perf_counter__ = perf_counter()
        peername = app.transport.get_extra_info('peername')

        app.r = await Packdata.add(
            __perf_counter__ = __perf_counter__,
            __exploited__ = app.__exploited__,
            __is_alive__ = app.__is_alive__,
            ip_host = peername[0],
            ip_port = peername[-1],
            peername = peername,
            __buff__ = bytearray(),
            __cap_buff__ = False,
            request = app.request,
            write = app.write,
            close = app.close,
            control = app.control,
            #pause_reading = app.transport.pause_reading,
            #resume_reading = app.transport.resume_reading,
            #is_reading = app.transport.is_reading,
        )

        await app.on_client_connected(app.r)
        
        await app.close()

        await Log.debug(f"Completed in {perf_counter() - app.r.__perf_counter__:.4f} seconds" )

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

    @classmethod
    async def init(app, **kwargs):
        app = app()
        app.__main__handler__ = app.serve_route

        app.__dict__.update(kwargs)
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
        
        if r.path not in app.memory["routes"]:
            memory = OrderedDict()
            actions = deque()
            memory["actions"] = actions

            if len(app.memory["routes"]) >= app.memory.get("max_routes_in_memory", 20):

                app.memory["routes"].popitem(last=False)

            app.memory["routes"][r.path] = memory

            # Handle before_middleware
            if (before_middleware := app.declared_routes.get("before_middleware")):
                actions.append(before_middleware.get("func"))

                await before_middleware.get("func")(r)

            if r.path in app.declared_routes:
                route = app.declared_routes[r.path]
                actions.append(route.get("func"))
                await route.get("func")(r)

            elif (handle_all_middleware := app.declared_routes.get("handle_all_middleware")):
                actions.append(handle_all_middleware.get("func"))

                await handle_all_middleware.get("func")(r)
            else:
                actions = OrderedDict()
                actions["raise"] = Abort
                actions["kwargs"] = {
                    "message": "Not Found",
                    "status": 404
                }

                memory["actions"] = actions

                raise actions["raise"](**actions["kwargs"])

            # Handle after_middleware
            if (after_middleware := app.declared_routes.get("after_middleware")):
                actions.append(after_middleware.get("func"))

                await after_middleware.get("func")(r)
                
        else:
            memory = app.memory["routes"][r.path]
            actions = memory["actions"]
        
            # Use memory to remember actions
            if isinstance(actions, deque):
                for action in actions:
                    await action(r)
                    await sleep(0)
                    
            elif isinstance(actions, OrderedDict):
                raise actions["raise"](**actions["kwargs"])
            else:
                raise Err("Something doesn't seem right.")

    async def handle_client(app, r):
        try:
            app.REQUEST_COUNT += 1
            r.identifier = app.REQUEST_COUNT
            await app.__main__handler__(r)

        except (Err, ServerGotInTrouble) as e:
            await Log.warning(r, e)

        except Abort as e:
            try:
                await e.text(r)
            except Err as e:
                pass
            except Exception as e:
                await Log.critical(r, e)

        except (ConnectionResetError, BrokenPipeError, CancelledError, Exception) as e:
            await Log.critical(r, e)

    async def run(app, HOST, PORT, **kwargs):
        app.server = await loop.create_server(
            lambda: Protocol(app.handle_client),
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