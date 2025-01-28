from ..Dependencies import *
from .request import *
from .streaming import *      
from gzip import compress, decompress
from asyncio import to_thread

class Simpleserve:
    __slots__ = (
        'headers',
        'cache_control',
        'CHUNK_SIZE',
        'r',
        'file_size',
        'filename',
        'file_stats',
        'last_modified',
        'etag',
        'last_modified_str',
        'file',
        'content_type',
        'content_disposition',
        'start',
        'end',
    )
    compressable = (
        "text/html",
        "text/css",
        "application/javascript",
        "application/json"
    )

    async def initialize(app, r, file: str, CHUNK_SIZE: int = 1024, **kwargs):
        app.r, app.file, app.CHUNK_SIZE = r, file, CHUNK_SIZE
        if not exists(app.file): raise Abort("Not Found", 404)

        app.headers = kwargs.get("headers", {
            "Accept-Ranges": "bytes"
        })

        app.cache_control = kwargs.get("cache_control", {
            "max-age": "3600"
        })

        return await app.prepare_metadata()

    async def validate_cache(app):
        if app.r.headers.get("If-None-Match") == app.etag:
            raise Abort("Not Modified", 304)

        elif (if_modified_since := app.r.headers.get("If-Modified-Since")) and strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT") >= gmtime(app.last_modified):
            raise Abort("Not Modified", 304)

    async def prepare_metadata(app):
        app.file_size = getsize(app.file)
        app.filename = basename(app.file)
        app.file_stats = stat(app.file)
        app.last_modified = app.file_stats.st_mtime
        
        app.etag = "BlazeIO--%s--%s" % (app.filename, app.file_size)

        app.last_modified_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(app.last_modified))
        
        if await app.validate_cache():
            return True

        app.content_type = guess_type(app.file)[0]

        if app.content_type:
            app.content_disposition = 'inline; filename="%s"' % app.filename
        else:
            app.content_type = "application/octet-stream"
            app.content_disposition = 'attachment; filename="%s"' % app.filename

        app.headers.update({
            "Content-Type": app.content_type,
            "Content-Disposition": app.content_disposition,
            "Last-Modified": app.last_modified_str,
            "Etag": app.etag,
            #"Content-Length": str(app.file_size),
        })
        
        if app.cache_control:
            app.headers["Cache-Control"] = "public, max-age=%s, must-revalidate" % app.cache_control.get("max-age", "3600")
            

        if (range_ := app.r.headers.get('Range')) and (idx := range_.rfind('=')) != -1:
            br = range_[idx + 1:]
            app.start = int(br[:br.rfind("-")])
            app.end = app.file_size - 1

            app.headers["Content-Range"] = "bytes %s-%s/%s" % (app.start, app.end, app.file_size)
        else:
            app.start, app.end = 0, app.file_size

    @classmethod
    async def push(cls, *args, **kwargs):
        app = cls()
        await app.initialize(*args, **kwargs)
        
        gzip = False
        if "gzip" in app.r.headers.get("Accept-Encoding", "") and kwargs.get("gzip") and app.content_type in app.compressable: gzip = True

        if gzip: app.headers["Content-Encoding"] = "gzip"

        await app.r.prepare(app.headers)
        
        if gzip: 
            if app.CHUNK_SIZE < 1024*1024:
                app.CHUNK_SIZE = 1024*1024

            async for chunk in app.pull():
                chunk = await to_thread(compress, chunk)
                await app.r.write(chunk)

        else:
            async for chunk in app.pull(): await app.r.write(chunk)

    async def pull(app):
        async with async_open(app.file, "rb") as f:
            f.seek(app.start)
            
            while (chunk := await f.read(app.CHUNK_SIZE)):
                yield chunk

                if app.start >= app.end: break

                app.start += len(chunk)

                f.seek(app.start)

if __name__ == "__main__":
    pass
