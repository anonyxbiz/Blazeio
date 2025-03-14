from ..Dependencies import *
from .streaming import *
from ..Client import Session

class RenderFreeTierPatch:
    def __init__(app, production = NotImplemented, host = None, asleep = 60):
        for method, value in locals().items():
            if method == app: continue
            setattr(app, method, value)

        if any([app.production, app.production == NotImplemented]):
            app.task = loop.create_task(app.keep_alive_render())
    
    async def _hello_world(app, r):
        await Deliver.text(r, "Hello World")

    async def keep_alive_render(app):
        await Log.debug("keep_alive_render initiating...")
        await Log.debug("keep_alive_render initiated...")

        while True:
            if not app.host:
                await sleep(5)
                continue
            try:
                async with Session("%s/hello/world" % app.host, "GET") as r: await r.aread()
            except CancelledError as e:
                raise e
            except Exception as e:
                await Log.critical(e)

            await sleep(app.asleep)

    async def before_middleware(app, r):
        if not app.host:
            if not (host := r.headers.get("Referer", r.headers.get("Origin"))):
                return
            
            if (id1 := host.find(v := "://")) != -1:
                if (id2 := host[(id1 := id1 + len(v)):].find("/")) != -1:
                    host = host[:id1 + id2]

            if app.production == NotImplemented:
                if not host.startswith("https://"):
                    app.production = False

            app.host = host

            await p("Added host as: %s" % app.host)
            
            if not app.production:
                try:
                    app.task.cancel()
                    await app.task
                except CancelledError:
                    await Log.debug("Quitted RenderFreeTierPatch as the app is not in production")
