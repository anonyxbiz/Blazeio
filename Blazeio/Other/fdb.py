import Blazeio as io

class Fdb:
    __slots__ = ("_master_lock")
    asyncQueues = {}
    def __init__(app, evloop = None):
        app._master_lock = io.ioCondition(evloop = evloop or io.ioConf.loop)

    async def obtain_lock(app, file):
        async with app._master_lock:
            if not (_lock := app.asyncQueues.get(file)):
                app.asyncQueues[file] = (lock := io.ioCondition())
            else:
                lock = _lock

        if not _lock: return

        async with lock:
            await lock.wait()

    async def release_lock(app, file):
        if not (lock := app.asyncQueues.get(file)): return

        async with lock:
            lock.notify(1)

        async with lock:
            if file in app.asyncQueues and not lock.waiter_count: app.asyncQueues.pop(file)

    async def update(app, file: str, data: (dict, bytes), encoding: str = "wb"):
        if isinstance(data, dict):
            data = io.dumps(data, indent=0).encode()

        if encoding != "ab": await app.obtain_lock(file)

        try:
            async with io.async_open(file, encoding) as f: await f.write(data)
        finally:
            if file in app.asyncQueues: await app.release_lock(file)

    async def read(app, file: str):
        async with io.async_open(file, "rb") as f: return io.loads(await f.read())

if __name__ == "__main__":
    pass