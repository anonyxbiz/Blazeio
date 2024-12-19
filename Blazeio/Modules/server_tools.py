from ..Dependencies import iopen, guess_type, basename, getsize, exists, Log, to_thread, deque, loop
from .request import Request
from .streaming import Abort      
from aiofiles import open as aiofilesiopen
from os import stat
from time import gmtime, strftime

class Simpleserve:
    def __init__(app, r, file: str, CHUNK_SIZE: int = 1024, headers={}, **kwargs):
        app.__dict__.update(locals())

        if not exists(app.file):
            raise Abort("Not Found", 404)
            
        app.ins = None

    async def __aexit__(app, ext_type, ext, tb):
        pass
            
    async def __aenter__(app):
        app.file_stats = stat(app.file)
        app.last_modified = app.file_stats.st_mtime
        app.last_modified_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(app.last_modified))

        app.if_modified_since = app.r.headers.get("If-Modified-Since")

        if app.if_modified_since and strptime(app.if_modified_since, "%a, %d %b %Y %H:%M:%S GMT") >= gmtime(app.last_modified):
            raise Abort("Not Modified", 304)

        app.file_size = getsize(app.file)

        app.content_type = guess_type(app.file)[0]
        app.content_disposition = 'inline; filename="%s"' % basename(app.file)

        app.headers.update({
            "Accept-Ranges": "bytes",
            "Content-Type": app.content_type,
            "Content-Disposition": app.content_disposition,
            "Last-Modified": app.last_modified_str,
            "Cache-Control": "public, max-age=3600"
        })

        if (range_header := app.r.headers.get('Range', None)) and (idx := range_header.rfind('=')) != -1:
            byte_range = range_header[idx + 1:]
            
            _ = byte_range.rfind("-")

            start = int(byte_range[:_])

            if byte_range[_ + 1:] == "":
                end = app.file_size - 1
            else:
                end = int(byte_range[_ + 1:])

            app.headers["Content-Range"] = "bytes %s-%s/%s" % (start, end, app.file_size)
        else:
            start, end = 0, app.file_size

        app.start, app.end, = start, end
        
        await app.r.prepare(app.headers)

        return app

    async def push(app):
        async with aiofilesiopen(app.file, "rb") as f:
            await f.seek(app.start)
            
            while True:
                if not (chunk := await f.read(app.CHUNK_SIZE)): break
    
                else: app.start += len(chunk)
                        
                await app.r.write(chunk)
                
                if app.start >= app.end:
                    break
                
                await app.r.control()


    async def pull(app):
        async with aiofilesiopen(app.file, "rb") as f:
            await f.seek(app.start)
            while True:
                if not (chunk := await f.read(app.CHUNK_SIZE)): break
    
                else: app.start += len(chunk)
                        
                yield chunk
                
                if app.start >= app.end: break
                
                else: await app.r.control()

if __name__ == "__main__":
    pass
