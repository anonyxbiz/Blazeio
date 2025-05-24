import Blazeio as io

scope = io.DotDict()

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*100, 1024*100

class App:
    __slots__ = ("hosts", "tasks", "protocols", "protocol_count", "host_update_event", "protocol_update_event", "timeout", "blazeio_proxy_hosts", "log",)

    def __init__(app, blazeio_proxy_hosts: str = "blazeio_proxy_hosts.txt", timeout: float = float(60*10), log: bool = False):
        app.blazeio_proxy_hosts = blazeio_proxy_hosts
        app.hosts = {}
        app.tasks = []
        app.log = log
        app.protocols = {}
        app.protocol_count = 0
        app.host_update_event = io.SharpEvent(True, io.ioConf.loop)
        app.protocol_update_event = io.SharpEvent(True, io.ioConf.loop)
        app.timeout = timeout

        app.tasks.append(io.ioConf.loop.create_task(app.update_file_db()))
        app.tasks.append(io.ioConf.loop.create_task(app.update_mem_db()))
        app.tasks.append(io.ioConf.loop.create_task(app.protocol_manager()))

    async def puller(app, r, resp):
        async for chunk in r.pull():
            await resp.write(chunk)
        
        await resp.eof()

    async def update_file_db(app):
        while await app.host_update_event.wait():
            async with io.async_open(app.blazeio_proxy_hosts, "wb") as f:
                await f.write(io.dumps(app.hosts).encode())

    async def update_mem_db(app):
        if not io.path.exists(app.blazeio_proxy_hosts): return

        async with io.async_open(app.blazeio_proxy_hosts, "rb") as f:
            app.hosts = io.loads(await f.read())

        await io.plog.cyan("update_mem_db", "loaded: %s" % io.dumps(app.hosts, indent=1))

    async def add_host(app, r):
        json = {(json := await io.Request.get_json(r)).get("host"): json.get("srv")}

        app.hosts.update(json)
        app.host_update_event.set()

        await io.plog.cyan("add_host", "added: %s" % io.dumps(json, indent=1))

        raise io.Abort("Added", 200)

    async def logger(app, r, i):
        await io.plog.cyan("%s:%d | %s@%s%s" % (r.ip_host, r.ip_port, r.method.upper(), i[-1], r.tail), ", ".join(["(%s=%s)" % (i, str(getattr(r, i, ""))[:100]) for i in r.__slots__]))

    async def protocol_manager(app, run = False):
        if not run:
            while await app.protocol_update_event.wait():
                await app.protocol_manager(True)
            return

        for i in app.protocols:
            if not (r := app.protocols.get(i)): continue

            if app.log: await app.logger(r, i)

            if (elapsed := float(io.perf_counter() - r.__perf_counter__)) >= app.timeout:
                r.cancel(str(io.Protocoltimeout()))
                app.protocols.pop(r.identifier)

    # Blazeio callback for a custom protocol
    async def __main_handler__(app, r: io.BlazeioProtocol):
        await io.Request.prepare_http_request(r)
        
        if (host := r.headers.get("Host", "")).startswith("localhost") and r.tail == "/$add_host":
            if r.ip_host != "127.0.0.1":
                raise io.Abort("Server could not be found", 503) # return generic response

            return await app.add_host(r)

        if not (remote := app.hosts.get(host)):
            raise io.Abort("Server could not be found", 503)

        app.protocol_count += 1
        r.identifier = (app.protocol_count, remote)
        r.__perf_counter__ = io.perf_counter()

        try:
            app.protocols[r.identifier] = r
            app.protocol_update_event.set()
            await app.proxy(r, remote)
        finally:
            app.protocols.pop(r.identifier)

    async def proxy(app, r: io.BlazeioProtocol, remote: str):
        task = None
        async with io.Session(remote + r.tail, r.method, r.headers, decode_resp=False) as resp:
            if r.method not in r.non_bodied_methods:
                task = io.create_task(app.puller(r, resp))

            await resp.prepare_http()

            await r.prepare(resp.headers, resp.status_code, encode_resp=False)

            async for chunk in resp.pull():
                await r.write(chunk)

            await r.eof()

            if task: await task

class Proxy:
    @classmethod
    async def add_to_proxy(app, host, port, proxy_port = 8080, in_try = False):
        if not in_try:
            try:
                return await app.add_to_proxy(host, port, proxy_port, True)
            except Exception as e:
                return await io.traceback_logger(e)

        async with io.Session("http://localhost:%d/$add_host" % proxy_port, "post", io.Rvtools.headers, json = {"host": host, "srv": "http://localhost:%d" % port}) as session:
            await io.plog.cyan("Proxy.add_to_proxy", await session.text())

add_to_proxy = Proxy.add_to_proxy

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-port", "--port", default = 8080)
    args = parser.parse_args()
    
    scope.web = io.App("0.0.0.0", int(args.port), __log_requests__=0)

    scope.web.attach(App())
    scope.web.runner()