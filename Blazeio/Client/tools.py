from ..Dependencies import *
from ..Modules.request import *

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

    async def write_chunked(app, data):
        if isinstance(data, (bytes, bytearray)):
            await app.protocol.push(b"%X\r\n%s\r\n" % (len(data), data))
        elif isinstance(data, (str, int)):
            raise Err("Only (bytes, bytearray, Iterable) are accepted")
        else:
            async for chunk in data:
                await app.protocol.push(b"%X\r\n%s\r\n" % (len(chunk), chunk))

            await app.write_chunked_eof()

    async def write_chunked_eof(app):
        await app.protocol.push(b"0\r\n\r\n")

    async def eof(app):
        if app.write == app.write_chunked:
            return await app.write_chunked_eof()

    async def save(app, filepath: str, mode: str = "wb"):
        async with async_open(filepath, mode) as f:
            async for chunk in app.pull(): await f.write(chunk)
    
    async def close(app, *args, **kwargs): return await app.__aexit__(*args, **kwargs)

if __name__ == "__main__":
    pass