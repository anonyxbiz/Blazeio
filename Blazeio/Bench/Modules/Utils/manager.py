# Blazeio.Bench.Modules.Utils.manager.py
import Blazeio as io

class Manager:
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

if __name__ == "__main__":
    ...