import Blazeio as io

class RenderFreeTierPatch:
    _is_on_render = io.is_on_render()
    def __init__(app, production = NotImplemented, host = None, rnd_host = None, asleep = 5):
        for method, value in locals().items():
            if method == app: continue
            setattr(app, method, value)

        app.host_resolved = io.SharpEvent()
        app.task = io.ioConf.loop.create_task(app.keep_alive_render())

    async def _hello_world(app, r):
        await io.Deliver.text("Hello World")

    async def keep_alive_render(app):
        await io.plog.debug("keep_alive_render initiating...")
        await app.host_resolved.wait_clear()

        await io.plog.debug("keep_alive_render initiated...")

        while True:
            async with io.Session("%s/hello/world" % app.rnd_host, "get", io.Rvtools.headers) as r:
                await r.text()
            await io.sleep(app.asleep)

    async def before_middleware(app, r):
        if not app.rnd_host and not app.host:
            if not (host := r.headers.get("Referer", r.headers.get("Origin"))):
                return

            if (id1 := host.find(v := "://")) != -1:
                if (id2 := host[(id1 := id1 + len(v)):].find("/")) != -1:
                    host = host[:id1 + id2]

            app.rnd_host = host
            app.host = host

            await io.plog.info("Added host as: %s" % app.rnd_host)
            app.host_resolved.set()