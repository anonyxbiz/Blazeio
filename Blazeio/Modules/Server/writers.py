# Blazeio.Modules.Server.writers
from ...Dependencies import *
from ...Dependencies.alts import *
from ..request import *
from ..streaming import *

class Batchedwriter:
    __slots__ = ("r", "buff", "min_chunk_size", "rem_chunk_size", "parent_write")
    def __init__(app, r = None, min_chunk_size: int = 1024*10):
        app.r, app.buff, app.min_chunk_size, app.rem_chunk_size = r, bytearray(), min_chunk_size, min_chunk_size*3

    async def __aenter__(app):
        if not app.r:
            app.r = Context._r()
        app.parent_write, app.r.write = app.r.write, app.write
        return app

    async def __aexit__(app, *args):
        if app.buff:
            await app.parent_write(bytes(app.buff))
        app.r.write = app.parent_write
        return False

    async def write(app, chunk):
        app.buff.extend(chunk)
        if len(app.buff) >= app.rem_chunk_size:
            view = memoryview(app.buff)
            _, app.buff = await app.parent_write(bytes(view[:app.min_chunk_size])), bytearray(bytes(view[app.min_chunk_size:]))

if __name__ == "__main__": ...