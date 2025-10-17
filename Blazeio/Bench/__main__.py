# Blazeio.Bench.__main__.py
import Blazeio as io

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*100, 1024*100

web = io.App("0.0.0.0", 6000, name = "web")

class Utils:
    def __init__(app): ...
    
    def total_duration(app):
        return sum([sum([request.duration for request in i.requests if isinstance(request.duration, (int, float))]) for i in app.analytics])/len(app.analytics)
        
    def remaining_time(app):
        if not app.analytics: return app.d
        return (app.d - app.total_duration())

    def session_active(app):
        return int(app.remaining_time())

    def done(app):
        return app.conns and all([conn.done() for conn in app.conns])
        
    async def log_timing(app, lineno: int = 10):
        async with app.sync_serializer:
            while not app.done():
                await io.plog.yellow("<line_%d>" % lineno, "detail: Bench Running", "conns: %d" % len(app.conns), "remaining_time: %s" % app.remaining_time(), func = app.log_timing)

                await io.sleep(0.01)

class Server:
    def __init__(app):
        app.payload = b"." * app.payload_size

    async def _tests_io_get(app, r: io.BlazeioProtocol, content: bytes = b"."*1024):
        await r.prepare({"Content-Type": r.headers.get("Content-type"), "Content-Length": str((len(content)*app.writes))}, 200)

        for i in range(app.writes):
            await r.writer(content)

class Client:
    def __init__(app): ...

    async def client(app, task_id):
        async with app.serializer: ...

        analytics = io.ddict(requests = [])

        r = await io.Session(app.url, prepare_http = False, send_headers = False, connect_only = True)

        app.analytics.append(analytics)

        while app.session_active():
            if not app.runner_notified:
                app.runner_notified = True
                app.serializer.notify_all()

            analytics.requests.append(request := io.ddict(latency = io.perf_timing(), ttfb = io.perf_timing(), prepare = io.perf_timing(), request_info = io.ddict(), duration = io.perf_timing()))

            if not app.is_local:
                await r.prepare(app.url, app.m, prepare_http = False)
            else:
                await r.writer(b'%b /tests/io/get HTTP/1.1\r\nHost: %b\r\n\r\n' % (app.m.encode(), r.host.encode()))
                r.status_code = 0

            request.prepare = request.prepare.get()

            request.ttfb_io = io.perf_timing() # Calculate the time it takes for a chunk to be received from server — waiting I/O involved here.

            await r.protocol.ensure_reading() # Ensure the transport is reading and wait for a chunk to be received from server if no chunk has been received yet.

            request.ttfb_io = request.ttfb_io.get()

            request.ttfb = request.ttfb.get()

            request.prepare_http = io.perf_timing()

            await r.prepare_http() # Receive chunks upto the http crlf that marks end of headers and build the request objects

            request.prepare_http = request.prepare_http.get()

            request.request_info.path, request.request_info.server_software = r.path, r.headers.get("server")

            request.body_io = io.perf_timing()

            body = bytearray()
            async for chunk in r:
                body.extend(chunk)

            request.body_io = request.body_io.get()
            request.transferred_bytes = len(body)

            request.latency = request.latency.get()
            request.duration = request.duration.get().elapsed
            if r.status_code >= 400: break

        return analytics

class Runner(Client, Utils):
    def __init__(app):
        app.runner_notified = False
        io.getLoop.create_task(app.runner())

    async def runner(app):
        await web # Wait for server to run

        async with app.serializer:
            for i in range(app.c):
                app.conns.append(io.getLoop.create_task(app.client(i)))
            await app.serializer.wait()
            io.getLoop.create_task(app.log_timing())

        async with io.perf_timing() as timer:
            await io.gather(*app.conns)

        async with app.sync_serializer: ...

        await io.plog.cyan(io.anydumps(io.ddict(
            Concurrency_level = app.c,
            **app.analytics[0].requests[0].request_info,
            session_duration = timer.get().elapsed,
            Total_requests = (Total_requests := sum([len(i.requests) for i in app.analytics])),
            duration = (duration := app.total_duration()),
            transferred_mbs = (transferred_mbs := sum([sum([request.transferred_bytes for request in i.requests]) for i in app.analytics])/(1024**2)),
            transfer_rate = (transferred_mbs/duration),
            Requests_per_second = (Total_requests/duration),
            Averages = io.ddict(**
                {
                    metric: {
                        metric_type: (sum([(sum([request.get(metric).get(metric_type) for request in i.requests])/len(i.requests)) for i in app.analytics])/len(app.analytics))
                        for metric_type in app.metric_types
                    }
                    for metric in app.request_metrics
                }
            ),
        )), func = app.runner)

        await io.Scope.web.exit()
        raise KeyboardInterrupt()

class Main(Server, Runner):
    __slots__ = ("c", "d", "payload_size", "url", "m", "payload", "serialize_connections", "conns", "writes", "runner_notified", "is_local", "analytics")
    serializer = io.ioCondition()
    sync_serializer = io.ioCondition()
    request_metrics = ("prepare", "prepare_http", "ttfb_io", "ttfb", "body_io", "latency")
    metric_types = ("elapsed", "rps")

    def __init__(app, url: (str, io.Utype) = ("http://%s:%d" % (web.ServerConfig.host, web.ServerConfig.port)) + "%s", c: (int, io.Utype) = 100, d: (int, io.Utype) = 10, m: (str, io.Utype) = "get", payload_size: (int, io.Utype) = 1024, writes: (int, io.Utype) = 1, conns: (list, io.Unone) = [], serialize_connections: (bool, io.Utype) = True, analytics: (list, io.Unone) = []):
        io.set_from_args(app, locals(), (io.Utype, io.Unone))
        app.is_local = app.url.startswith("http://%s:%d" % (web.ServerConfig.host, web.ServerConfig.port))
        io.Super(app).__init__()

if __name__ == "__main__":
    # clear && py -m Blazeio.Versioning -update -quiet && clear && py -m Blazeio.Bench
    from Blazeio.Other.class_parser import Parser
    parser = Parser(Main, io.Utype)

    with web:
        web.with_keepalive()
        web.attach(Main(**parser.args()))
        web.runner()
