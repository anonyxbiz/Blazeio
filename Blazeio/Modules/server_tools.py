from ..Dependencies import *
from .request import *
from .streaming import *      

class Simpleserve:
    CHUNK_SIZE: int = 1024
    headers: dict = {
        "Accept-Ranges": "bytes"
    }
    cache_control: dict = {
        "max-age": "3600"
    }

    async def initialize(app, r, file: str, CHUNK_SIZE: int = 1024, **kwargs):
        if not exists(file): raise Abort(status = 404, reason = "Not Found")

        app.r, app.file, app.CHUNK_SIZE = r, file, CHUNK_SIZE

        if kwargs: app.__dict__.update(**kwargs)

        await app.prepare_metadata()

    async def validate_cache(app):
        if (if_modified_since := app.r.headers.get("If-Modified-Since")) and strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT") >= gmtime(app.last_modified):
            raise Abort("Not Modified", status=304, reason="Not Modified")
            
        elif (if_none_match := app.r.headers.get("If-None-Match")):
            if if_none_match == app.etag:
                raise Abort("Not Modified", status=304, reason="Not Modified")

    async def prepare_metadata(app):
        app.file_size = getsize(app.file)
        app.filename = basename(app.file)
        app.file_stats = stat(app.file)
        app.last_modified = app.file_stats.st_mtime
        
        app.etag = "BlazeIO--%s--%s" % (app.filename, app.file_size)

        app.last_modified_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(app.last_modified))
        
        await app.validate_cache()

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
            "Etag": app.etag
        })
        
        if app.cache_control:
            app.headers["Cache-Control"] = "public, max-age=%s, must-revalidate" % app.cache_control.get("max-age", "3600")
            

        if (range_header := app.r.headers.get('Range')) is not None and (idx := range_header.rfind('=')) != -1:
            byte_range = range_header[idx + 1:]
            
            _ = byte_range.rfind("-")

            app.start = int(byte_range[:_])

            if byte_range[_ + 1:] == "":
                app.end = app.file_size - 1
            else:
                app.end = int(byte_range[_ + 1:])

            app.headers["Content-Range"] = "bytes %s-%s/%s" % (app.start, app.end, app.file_size)
        else:
            app.start, app.end = 0, app.file_size

        return app

    @classmethod
    async def push(cls, *args, **kwargs):
        app = cls()
        await app.initialize(*args, **kwargs)

        await app.r.prepare(app.headers)
        async for chunk in app.pull():
            await app.r.write(chunk)

    async def pull(app):
        async with iopen(app.file, "rb") as f:
            await f.seek(app.start)
            
            while True:
                if not (chunk := await f.read(app.CHUNK_SIZE)): break
                
                yield chunk

                if app.start >= app.end: break

                app.start += len(chunk)
                
                await sleep(0)

if __name__ == "__main__":
    pass
