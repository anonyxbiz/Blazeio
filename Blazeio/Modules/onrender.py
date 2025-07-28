from Blazeio import *

is_on_render = lambda: environ.get("RENDER")

class RenderFreeTierPatch:
    _is_on_render = is_on_render()
    def __init__(app, production = NotImplemented, host = None, rnd_host = None, asleep = 5):
        if not app._is_on_render: return
        app.host_resolved = SharpEvent()

        for method, value in locals().items():
            if method == app: continue
            setattr(app, method, value)

        if any([app.production, app.production == NotImplemented]):
            app.task = loop.create_task(app.keep_alive_render())
    
    async def _hello_world(app, r):
        await Deliver.text("Hello World")

    async def keep_alive_render(app):
        await Log.debug("keep_alive_render initiating...")
        await app.host_resolved.wait_clear()

        await Log.debug("keep_alive_render initiated...")

        while True:
            async with io.Session.get("%s/hello/world" % app.rnd_host, ) as r: await r.aread()
            await sleep(app.asleep)

    async def before_middleware(app, r):
        if not app.rnd_host and not app.host:
            if not (host := r.headers.get("Referer", r.headers.get("Origin"))):
                return

            if (id1 := host.find(v := "://")) != -1:
                if (id2 := host[(id1 := id1 + len(v)):].find("/")) != -1:
                    host = host[:id1 + id2]

            if app.production == NotImplemented:
                if not host.startswith("https://"):
                    app.production = False

            app.rnd_host = host
            app.host = host

            await p("Added host as: %s" % app.rnd_host)
            app.host_resolved.set()