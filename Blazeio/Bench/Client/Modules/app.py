# Blazeio.Bench.Client.Modules.app.py
import Blazeio as io

class Utils:
    def __init__(app): ...
    
    def total_duration(app):
        return sum([sum([request.duration for request in i.requests if isinstance(request.duration, (int, float))]) for i in app.analytics])/len(app.analytics)

    def remaining_time(app):
        if not app.analytics: return app.d
        return (app.d - (io.perf_counter() - app.perf_counter))

    def session_active(app):
        return int(app.remaining_time())

    def done(app):
        return app.conns and all([conn.done() for conn in app.conns])
        
    async def log_timing(app, lineno: int = 15):
        async with app.sync_serializer:
            while not app.done():
                await io.plog.yellow("<line_%d>" % lineno, "detail: Bench Running", "conns: %d" % len(app.conns), "remaining_time: %s" % app.remaining_time(), func = app.log_timing)

                await io.sleep(0.05)

class Client(Utils):
    __slots__ = ()
    def __init__(app):
        app.runner_notified = False

    async def runner(app):
        async with app.serializer:
            for i in range(app.c):
                app.conns.append(io.getLoop.create_task(app.client(i)))

            await app.serializer.wait()

        app.perf_counter = io.perf_counter()

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
        )))

    async def client(app, task_id):
        async with app.serializer: ...

        analytics = io.ddict(requests = [])

        app.analytics.append(analytics)

        while app.session_active():
            if not app.runner_notified:
                app.runner_notified = True
                app.serializer.notify_all()

            analytics.requests.append(request := io.ddict(latency = io.perf_timing(), ttfb = io.perf_timing(), prepare = io.perf_timing(), request_info = io.ddict(), duration = io.perf_timing()))
            
            async with io.getSession(app.url, app.m, prepare_http = False) as r:
                request.prepare = request.prepare.get()
    
                request.ttfb_io = io.perf_timing() # Calculate the time it takes for a chunk to be received from server — waiting I/O involved here.
    
                await r.protocol.ensure_reading() # Ensure the transport is reading and wait for a chunk to be received from server if no chunk has been received yet.
    
                request.ttfb_io = request.ttfb_io.get()
    
                request.ttfb = request.ttfb.get()
    
                request.http_parsing = io.perf_timing()

                await r.prepare_http()
    
                request.http_parsing = request.http_parsing.get()
    
                request.request_info.path, request.request_info.server_software = r.path, r.headers.get("server")
    
                request.body_io = io.perf_timing()
    
                body = bytearray()
                async for chunk in r:
                    body.extend(chunk)
    
                request.body_io = request.body_io.get()
                request.transferred_bytes = len(body)

                request.latency = request.latency.get()
                request.duration = request.duration.get().elapsed

        return analytics

if __name__ == "__main__":
    ...