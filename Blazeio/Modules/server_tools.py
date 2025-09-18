from ..Dependencies import *
from .request import *
from .streaming import *

class Simpleserve:
    __slots__ = ('headers','cache_control','CHUNK_SIZE','r','file_size','filename','file_stats','last_modified','etag','last_modified_str','file','content_type','content_disposition','start','end','range_','status', 'exclude_headers')
    compressable = ("text/html","text/css","text/javascript","text/x-python","application/javascript","application/json")

    headers_demux = ddict(content_type = "Content-Type", content_length = "Content-Length", content_disposition = "Content-Disposition", last_modified_str = "Last-Modified", etag = "Etag")
    def __init__(app, r = None, file: str = "", CHUNK_SIZE: int = 1024, headers: dict = {"Accept-ranges": "bytes"}, cache_control = {"max-age": "0"}, status: int = 200, exclude_headers: tuple = (), **kwargs):
        if r and file:
            app.r, app.file, app.CHUNK_SIZE, app.headers, app.cache_control, app.status, app.exclude_headers = r, file, CHUNK_SIZE, dict(headers), cache_control, status, exclude_headers
            if not path.exists(app.file): raise NotFoundErr("Not Found", 404)

    def initialize(app, *args, **kwargs):
        if args or kwargs: app.__init__(*args, **kwargs)

        return app.prepare_metadata()

    def validate_cache(app):
        if app.r.headers.get("If-none-match") == app.etag:
            raise Abort("Not Modified"*85, 304)

        elif (if_modified_since := app.r.headers.get("If-modified-since")) and strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT") >= gmtime(app.last_modified):
            raise Abort("Not Modified"*85, 304)
    
    def __await__(app):
        yield from app.prepare_metadata().__await__()
        return app

    async def prepare_metadata(app):
        if not hasattr(app, "file_size"):
            app.file_size = path.getsize(app.file)

        if not hasattr(app, "filename"):
            app.filename = path.basename(app.file)

        app.file_stats = stat(app.file)
        app.last_modified = app.file_stats.st_mtime

        if not hasattr(app, "etag"):
            app.etag = "BlazeIO--%s--%s" % (app.filename, app.file_size)

        app.last_modified_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(app.last_modified))

        if app.validate_cache(): return True

        app.content_type = guess_type(app.file)[0]

        if app.content_type:
            app.content_disposition = 'inline; filename="%s"' % app.filename
        else:
            app.content_type = "application/octet-stream"
            app.content_disposition = 'attachment; filename="%s"' % app.filename

        for i in app.headers_demux:
            if app.headers_demux[i] not in app.exclude_headers and i in app.__slots__:
                app.headers[app.headers_demux[i]] = getattr(app, i)

        if app.cache_control:
            if not (i := "Cache-control") in app.exclude_headers:
                app.headers[i] = "public, max-age=%s, must-revalidate" % app.cache_control.get("max-age", "3600")

        if (range_ := app.r.headers.get('Range')) and (idx := range_.rfind('=')) != -1:
            app.range_ = range_
            br = range_[idx + 1:]
            app.start = int(br[:br.rfind("-")])
            app.end = app.file_size - 1

            app.headers["Content-Range"] = "bytes %s-%s/%s" % (app.start, app.end, app.file_size)
            app.status = 206
        else:
            app.start, app.end, app.range_ = 0, app.file_size, range_

            if not app.headers_demux.content_length in app.exclude_headers:
                app.headers[app.headers_demux.content_length] = str(app.file_size)

            app.status = 200

    @classmethod
    async def push(cls, *args, **kwargs):
        app = cls()
        await app.initialize(*args, **kwargs)

        if kwargs.get("encode", None) and app.content_type in app.compressable:
            if (encoding := app.r.headers.get("Accept-encoding")):
                for encoder in ("gzip", "br"):
                    if encoder in encoding:
                        app.headers["Content-encoding"] = encoder
                        break

        await app.r.prepare(app.headers, app.status)

        async for chunk in app.pull(): await app.r.write(chunk)

    async def pull(app):
        async with async_open(app.file, "rb") as f:
            if app.start: f.seek(app.start)

            while (chunk := await f.read(app.CHUNK_SIZE)):
                yield chunk

                if app.start >= app.end: break
                app.start += len(chunk)
                f.seek(app.start)
    
    async def __aenter__(app):
        await app.prepare_metadata()
        return app

    async def __aexit__(app, ext_t, ext_v, tb):
        if ext_v: raise ext_v

    async def __aiter__(app):
        async for chunk in app.pull(): yield chunk

if __name__ == "__main__": ...