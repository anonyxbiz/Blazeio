from ..Dependencies import *
from ..Dependencies.alts import *
from .request import *
from .streaming import *

class Simpleserve:
    __slots__ = ('headers','cache_control','CHUNK_SIZE','r','file_size','filename','file_stats','last_modified','etag','last_modified_str','file','content_type','content_disposition','start','end','range_','status', 'exclude_headers', 'inline', 'attachment')
    mimetypes_add_type('image/webp', '.webp')
    compressable = ("text/html","text/css","text/javascript","text/x-python","application/javascript","application/json")
    headers_demux = ddict(content_type = "Content-Type", content_length = "Content-Length", content_disposition = "Content-Disposition", last_modified_str = "Last-Modified", etag = "Etag")
    rare_validation = ("image", "video",)
    def __init__(app, r = None, file: str = "", CHUNK_SIZE: int = 1024, headers: dict = {"Accept-ranges": "bytes"}, cache_control = {"max-age": "3600"}, status: int = 200, exclude_headers: tuple = (), inline: bool = 0, attachment: bool = 0, **kwargs):
        if r and file:
            app.r, app.file, app.CHUNK_SIZE, app.headers, app.cache_control, app.status, app.exclude_headers, app.inline, app.attachment = r, file, CHUNK_SIZE, dict(headers), cache_control, status, exclude_headers, inline, attachment
            if not path.exists(app.file): raise NotFoundErr("Not Found", 404)

    def initialize(app, *args, **kwargs):
        if args or kwargs: app.__init__(*args, **kwargs)

        return app.prepare_metadata()
    
    def is_modified(app):
        if not (if_modified_since := app.r.headers.get("If-modified-since")): return NotImplemented

        if strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT") == strptime(app.last_modified_str, "%a, %d %b %Y %H:%M:%S GMT"):
            raise Abort("", 304, app.headers)
    
    def is_match(app):
        if not (etag := app.r.headers.get("If-none-match")): return

        if etag == app.etag:
            raise Abort("", 304, app.headers)

    def validate_cache(app):
        if app.is_modified() is NotImplemented:
            app.is_match()

    def validate_method(app):
        if app.r.method == "GET": ...
        elif app.r.method == "HEAD": ...
        else: raise Abort("Method %s is not allowed for this resource" % app.r.method, 405, ddict(Allow = "GET, HEAD"))

    def __await__(app):
        yield from app.prepare_metadata().__await__()
        return app

    def __aiter__(app):
        return app.pull()

    def prepare_metadata(app):
        if not hasattr(app, "file_size"):
            app.file_size = path.getsize(app.file)

        if not hasattr(app, "filename"):
            app.filename = path.basename(app.file)

        app.file_stats = stat(app.file)

        app.last_modified = app.file_stats.st_mtime

        if not hasattr(app, "etag"):
            app.etag = "BlazeIO--%s--%s" % (app.filename, app.file_size)

        app.last_modified_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(app.last_modified))

        app.content_type = guess_type(app.file)[0]

        if not app.content_type:
            app.content_type = "application/octet-stream"
            app.attachment = 1

        if app.attachment:
            app.content_disposition = 'attachment; filename="%s"' % app.filename
        else:
            app.content_disposition = 'inline; filename="%s"' % app.filename

        for i in app.headers_demux:
            if app.headers_demux[i] not in app.exclude_headers and i in app.__slots__:
                if (val := getattr(app, i, None)):
                    app.headers[app.headers_demux[i]] = val

        if app.cache_control:
            if not (i := "Cache-control") in app.exclude_headers:
                app.headers[i] = "public, max-age=%s%s" % (app.cache_control.get("max-age", "3600"), ", must-revalidate" if app.content_type[:app.content_type.find("/")] not in app.rare_validation else "")

        if (range_ := app.r.headers.get('Range')) and (idx := range_.rfind('=')) != -1:
            app.range_ = range_
            br = range_[idx + 1:]
            _ = br.find("-")
            start, end = br[:_], br[_ + 1:]
            app.start, app.end = int(start), int(end) if end else app.file_size - 1

            if app.end > app.file_size:
                raise Abort("Range Not Satisfiable", 416, {"Content-Range": "bytes */%d" % app.file_size, "Content-Type": app.content_type})

            app.headers["Content-Range"] = "bytes %s-%s/%s" % (app.start, app.end, app.file_size)
            app.status = 206
        else:
            app.start, app.end, app.range_ = 0, app.file_size, range_
            app.status = 200
        
        if not app.headers_demux.content_length in app.exclude_headers:
            app.headers[app.headers_demux.content_length] = str(app.end - app.start)

        if app.validate_cache(): return True
        
        app.validate_method()
        return AsyncSyncCompatibilityInstance

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
        async with async_open(app.file, "rb") as fd:
            if app.start: fd.seek(app.start)
            while (chunk := await fd.read(app.CHUNK_SIZE)):
                yield chunk
    
                if app.start >= app.end: break
                app.start += len(chunk)
                fd.seek(app.start)

    async def aread(app, size: int):
        async with async_open(app.file, "rb") as fd:
            if app.start: fd.seek(app.start)
            chunk = await fd.read(size)
            app.start += len(chunk)
            return chunk

    async def __aenter__(app):
        app.prepare_metadata()
        return app

    async def __aexit__(app, ext_t, ext_v, tb):
        return False

class StaticServer:
    __slots__ = ("root", "root_dir", "chunk_size", "page_dir", "home_page")
    ext_delimiter: str = "."
    html_ext: str = ".html"
    pop_chunked_headers = ("Content-Length", "Content-Range")
    def __init__(app, root: str, root_dir: str, chunk_size: int, page_dir: str = "page", home_page: str = "index.html"):
        app.root, app.root_dir, app.chunk_size, app.page_dir, app.home_page = root, root_dir, chunk_size, page_dir, home_page

    async def handle_all_middleware(app, r: BlazeioProtocol):
        if r.path[:len(app.root)] != app.root: return

        if not path.exists(file_path := path.join(app.root_dir, route) if app.ext_delimiter in (route := r.path[1:] or path.join(app.page_dir, app.home_page)) else path.join(app.root_dir, app.page_dir, route + app.html_ext)):
            raise Abort("Not found", 404)

        async with Simpleserve(r, file_path, app.chunk_size) as f:
            await r.prepare(f.headers, f.status)
            async for chunk in f:
                await r.write(chunk)

if __name__ == "__main__": ...