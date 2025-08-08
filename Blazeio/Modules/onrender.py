import Blazeio as io

class RenderFreeTierPatch:
    def __init__(app, host = None, rnd_host = None, asleep = 30):
        for method, value in locals().items():
            if method == app: continue
            setattr(app, method, value)

        app.host_resolved = io.SharpEvent()
        app.request_count = 0
        app.e = None
        app.task = io.ioConf.loop.create_task(app.keep_alive_render())

    async def _hello_world(app, r):
        app.request_count += 1
        await io.Deliver.text("Hello World@%s" % io.perf_counter())

    async def _rftp_request_count(app, r):
        await io.Deliver.json(io.ddict(request_count = app.request_count, e = app.e))

    async def keep_alive_render(app):
        await io.plog.debug("keep_alive_render initiating...")
        await app.host_resolved.wait_clear()
        await io.plog.debug("keep_alive_render initiated...")

        async with io.Ehandler() as e:
            while True:
                async with io.Session("%s/hello/world" % app.host, "get", io.Rvtools.headers, params = io.ddict(perf_counter=io.perf_counter())) as r:
                    await r.text()
                await io.sleep(app.asleep)

        if e.err:
            app.e = str(e.err)

    async def before_middleware(app, r):
        if not app.host:
            if not (url := r.headers.get("Referer", r.headers.get("Origin", r.headers.get("Host")))):
                return

            try: app.host, port, _ = io.ioConf.url_to_host(url, {})
            except TypeError: return

            if port == 443:
                app.host = "https://%s" % app.host
            else:
                app.host = "http://%s:%s" % (app.host, port)
    
            await io.plog.info("Added host as: %s" % app.host)
            app.host_resolved.set()