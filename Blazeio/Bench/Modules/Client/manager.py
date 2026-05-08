# Blazeio.Bench.Modules.Client.manager.py
import Blazeio as io

class Manager:
    def __init__(app): ...

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
                if app.is_local:
                    r.status_code = 0

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