# Blazeio.Bench.__main__.py
import Blazeio as io

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*4, 1024*4

web = io.App("0.0.0.0", 6000)

class App:
    serializer = io.ioCondition()
    def __init__(app, connections: (int, io.Utype) = 10, duration: (int, io.Utype) = 10, payload_size: (int, io.Utype) = 1024*1, url: (str, io.Utype) = "http://%s:%d/post" % (web.ServerConfig.host, web.ServerConfig.port)):
        io.set_from_args(app, locals(), io.Utype)
        app.payload = b"." * app.payload_size
        app.perf_counter = None
        io.getLoop.create_task(app.runner())

    async def runner(app):
        await web # Wait for server to run
        
        conns = []
        async with app.serializer:
            for i in range(app.connections):
                conns.append(io.getLoop.create_task(app.client(i)))
            app.perf_counter = io.perf_counter()
        
        analytics = await io.gather(*conns)
        
        total_requests = sum([i.requests for i in analytics])

        await io.plog.cyan(io.dumps({"Total_requests": total_requests}))

        raise KeyboardInterrupt()

    async def _post(app, r):
        await r.prepare(r.headers, 200)

        async for chunk in r.pull():
            await r.write(chunk)

    async def client(app, task_id):
        async with app.serializer: ...

        analytics = io.ddict(tasks_created = io.perf_timing())
        analytics.timings = {}
        analytics.requests = 0
        analytics.tasks_created()
        analytics.base_line_reference_dict_creation = io.perf_timing() # Used to compare the benchmarks universally
        dict()
        analytics.base_line_reference_dict_creation()

        while (io.perf_counter() - app.perf_counter) < app.duration:
            timing = io.perf_timing()
            async with io.getSession.post(app.url, body = io.dumps(io.ddict(task_id = task_id, now = io.timef.now(io.UTC), payload = app.payload)).encode()) as r:
                text = await r.text()

            timing()
            analytics.timings["last_request_timing"] = timing.get()
            analytics.requests += 1

        return analytics

if __name__ == "__main__":
    from Blazeio.Other.class_parser import Parser
    parser = Parser(App, io.Utype)
    args = parser.parse_args()

    with web:
        web.with_keepalive()
        web.attach(App(**args.__dict__))
        web.runner()
