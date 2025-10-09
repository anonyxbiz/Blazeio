# Blazeio.Bench.__main__.py
import Blazeio as io

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*4, 1024*4

web = io.App("0.0.0.0", 6000, name = "web")

class Server:
    def __init__(app):
        app.payload = b"." * app.payload_size

    async def _tests_io_raw_get(app, r: io.BlazeioProtocol, content = b"."*1024, status = 200):
        await r.writer(
            b'HTTP/1.1 %d %b\r\n' % (status, io.StatusReason.reasons.get(status, "Unknown").encode()) +
            b'Server: %b\r\n' % ("Blazeio/%s (%s)" % (io.__version__, io.os_name)).encode() +
            b'Content-Type: text/plain\r\n' +
            b'Content-disposition: inline; filename="%b.txt"\r\n' % r.path.encode() +
            b'Content-Length: %d\r\n' % len(content) +
            b'\r\n'
        )
        
        if r.method in r.no_response_body_methods: raise io.Eof()

        await r.writer(content)

class Client:
    def __init__(app): ...

    async def client(app, task_id):
        async with app.serializer: ...

        analytics = io.ddict(requests = [])

        async with io.Session(app.url, prepare_http = False, send_headers = False, connect_only = True) as conn:
            while app.available_time():
                analytics.requests.append(request := io.ddict(latency = io.perf_timing(), ttfb = io.perf_timing(), prepare = io.perf_timing(), request_info = io.ddict()))

                r = await conn.prepare((app.url % "/tests/io/raw/get") if app.url.startswith("http://%s:%d" % (web.ServerConfig.host, web.ServerConfig.port)) else app.url, app.m.upper(), prepare_http = False) # Convert the objects into a http/1.1 request and send it without preparing the response — No I/O involved here.

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

                body = await r.aread() # Receive the response body

                request.body_io = request.body_io.get()

                request.latency = request.latency.get()

        return analytics

class Utils:
    def __init__(app): ...

    def available_time(app):
        return (io.perf_counter() - app.perf_counter) < app.d

    async def log_timing(app, lineno: int = 10):
        async with app.sync_serializer:
            while app.available_time():
                await io.plog.yellow("<line_%d>" % lineno, io.dumps(io.ddict(detail = "Bench Running", conns = len(app.conns), remaining_time = (io.perf_counter() - app.perf_counter)), indent=2), func = app.log_timing)
                await io.sleep(0.1)

class Runner(Client, Utils):
    def __init__(app):
        io.getLoop.create_task(app.runner())

    async def runner(app):
        await web # Wait for server to run
        
        if app.serialize_connections: await app.serializer.__aenter__()

        for i in range(app.c):
            app.conns.append(io.getLoop.create_task(app.client(i)))

        app.perf_counter = io.perf_counter()
        io.getLoop.create_task(app.log_timing())

        if app.serialize_connections: await app.serializer.__aexit__()

        analytics = await io.gather(*app.conns)

        async with app.sync_serializer: ...

        await io.plog.cyan(io.anydumps(io.ddict(
            Total_requests = sum([len(i.requests) for i in analytics]),
            Concurrency_level = app.c,
            **analytics[0].requests[0].request_info,
            Averages = io.ddict(**
                {
                    metric: {
                        metric_type: (sum([(sum([request.get(metric).get(metric_type) for request in i.requests])/len(i.requests)) for i in analytics])/len(analytics))
                        for metric_type in app.metric_types
                    }
                    for metric in app.request_metrics
                }
            ),
        )), func = app.runner)

        await io.Scope.web.exit()
        raise KeyboardInterrupt()

class Main(Server, Runner):
    __slots__ = ("c", "d", "payload_size", "url", "m", "payload", "serialize_connections", "conns")
    serializer = io.ioCondition()
    sync_serializer = io.ioCondition()
    request_metrics = ("prepare", "prepare_http", "ttfb_io", "ttfb", "body_io", "latency")
    metric_types = ("elapsed", "rps")

    def __init__(app, url: (str, io.Utype) = ("http://%s:%d" % (web.ServerConfig.host, web.ServerConfig.port)) + "%s", c: (int, io.Utype) = 100, d: (int, io.Utype) = 5, m: (str, io.Utype) = "head", payload_size: (int, io.Utype) = 1024, conns: (list, io.Unone) = [], serialize_connections: (bool, io.Utype) = True, perf_counter: (None, io.Unone) = None):
        io.set_from_args(app, locals(), (io.Utype, io.Unone))
        io.Super(app).__init__()

if __name__ == "__main__":
    from Blazeio.Other.class_parser import Parser
    parser = Parser(Main, io.Utype)

    with web:
        web.with_keepalive()
        web.attach(Main(**parser.args()))
        web.runner()
