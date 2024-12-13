from ..Dependencies import iopen, guess_type, basename, getsize, exists, Log, to_thread, deque, loop
from .request import Request
from .streaming import Abort      
from aiofiles import open as aiofilesiopen

class Simpleserve:
    def __init__(app, r, file: str, CHUNK_SIZE: int = 1024, headers={}, **kwargs):
        app.__dict__.update(locals())

        if not exists(app.file):
            raise Abort("Not Found", 404)
            
        app.ins = None
        
    async def __aexit__(app, ext_type, ext, tb):
        if app.ins is not None: await app.ins.close()

    async def __aenter__(app):
        app.file_size = getsize(app.file)

        app.headers.update({
            "Accept-Ranges": "bytes",
            "Content-Type": guess_type(app.file)[0],
            "Content-Disposition": f'inline; filename="{basename(app.file)}"'
        })
        
        if range_header := app.r.headers.get('Range', None):
            byte_range = range_header.strip().split('=')[1]
            _ = byte_range.split('-')
            start = int(_[0])

            if _[-1] == "":
                end = app.file_size - 1
            else:
                end = int(_[-1])
            
        else:
            start, end = 0, app.file_size
            
        if range_header:
            app.headers["Content-Range"] = "bytes %s-%s/%s" % (start, end, app.file_size)

        app.start, app.end, = start, end
        
        await app.r.prepare(app.headers)

        return app
        
    async def push(app):
        app.ins = await aiofilesiopen(app.file, "rb")

        await app.ins.seek(app.start)
        while True:
            if not (chunk := await app.ins.read(app.CHUNK_SIZE)): break

            else: app.start += len(chunk)
                    
            await app.r.write(chunk)
            
            if app.start >= app.end: break
            
            else: await app.r.control()


    async def pull(app):
        app.ins = await aiofilesiopen(app.file, "rb")

        await app.ins.seek(app.start)
        while True:
            if not (chunk := await app.ins.read(app.CHUNK_SIZE)): break

            else: app.start += len(chunk)
                    
            yield chunk
            
            if app.start >= app.end: break
            
            else: await app.r.control()

if __name__ == "__main__":
    pass
