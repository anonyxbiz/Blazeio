from ..Dependencies import *
from ..Modules.request import *
from zlib import decompressobj, MAX_WBITS as zlib_MAX_WBITS
from brotlicffi import Decompressor

class Toolset:
    __slots__ = ()
    def __init__(app):
        pass

    async def json(app):
        data = bytearray()
        async for chunk in app.pull():
            if chunk:
                data.extend(chunk)
        return loads(data.decode("utf-8"))

    async def find(app, *args):
        data, start, end, cont = args
        while (idx := data.find(start)) != -1:
            await sleep(0)
            data = data[idx + len(start):]

            if (ids := data.find(end)) != -1:
                chunk, data = data[:ids], data[ids + len(end):]

                if start in chunk:
                    async for i in app.find(chunk, *args[1:]):
                        yield (start + i + end if cont else i, data)
                else:
                    yield (start + chunk + end if cont else chunk, data)

    async def aextract(app, start: (bytes, bytearray), end: (bytes, bytearray), cont=True):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)
            async for x, data in app.find(data, start, end, cont):
                yield x
    
    async def brotli(app):
        decompressor = await to_thread(Decompressor)
        async for chunk in app.handler():
            yield await to_thread(decompressor.decompress, bytes(chunk))

    async def gzip(app):
        decompressor = decompressobj(16 + zlib_MAX_WBITS)

        async for chunk in app.handler():
            yield decompressor.decompress(bytes(chunk))

        if (chunk := decompressor.flush()):
            yield chunk

if __name__ == "__main__":
    pass