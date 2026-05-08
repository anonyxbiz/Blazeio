# Blazeio.Bench.Modules.Runner.manager.py
import Blazeio as io

class Manager:
    def __init__(app):
        app.runner_notified = False
        if not app.server_only:
            io.getLoop.create_task(app.runner())

    async def runner(app):
        await io.Scope.web # Wait for server to run

        async with app.serializer:
            for i in range(app.c):
                app.conns.append(io.getLoop.create_task(app.client(i)))

            await app.serializer.wait()

            # io.getLoop.create_task(app.log_timing())
        
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
        )), func = app.runner)

        await io.Scope.web.exit()
        raise KeyboardInterrupt()

if __name__ == "__main__":
    ...