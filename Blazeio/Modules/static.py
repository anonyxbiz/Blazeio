from ..Dependencies import iopen, guess_type, basename, getsize, exists, Log
from ..Dependencies import p, Err, Packdata, join, to_thread, gzip_compress
from .request import Request
from .streaming import Stream, Deliver, Abort      

class StaticFileHandler:
    CHUNK_SIZE = 1024
    @classmethod
    async def prepare(app, r, file_path, headers={}, CHUNK_SIZE=None):

        if not exists(file_path):
            raise Abort("File Not Found", 404, reason="Not Found")

        r.StaticFileHandler = await Packdata.add(file_path=file_path, headers=headers, CHUNK_SIZE=CHUNK_SIZE or StaticFileHandler.CHUNK_SIZE)

        r.StaticFileHandler.filename = basename(r.StaticFileHandler.file_path)
        r.StaticFileHandler.file_size = getsize(r.StaticFileHandler.file_path)
        r.StaticFileHandler.content_type, _ = guess_type(r.StaticFileHandler.file_path)

        r.StaticFileHandler.content_disposition = f'inline; filename="{r.StaticFileHandler.filename}"'

        if range_header := r.headers.get('Range'):
            r.StaticFileHandler.range_header = range_header
            r.StaticFileHandler.byte_range = r.StaticFileHandler.range_header.strip().split('=')[1]
            r.StaticFileHandler.start, r.StaticFileHandler.end = r.StaticFileHandler.byte_range.split('-')
            r.StaticFileHandler.start = int(r.StaticFileHandler.start)
            r.StaticFileHandler.end = int(r.StaticFileHandler.end) if r.StaticFileHandler.end else r.StaticFileHandler.file_size - 1
        else:
            r.StaticFileHandler.range_header = None
            r.StaticFileHandler.start, r.StaticFileHandler.end = 0, r.StaticFileHandler.file_size - 1

        r.StaticFileHandler.content_length = str(r.StaticFileHandler.end - r.StaticFileHandler.start + 1)

        if not r.StaticFileHandler.content_type:
            r.StaticFileHandler.content_type = "application/octet-stream"
            r.StaticFileHandler.content_disposition = f'attachment; filename="{r.StaticFileHandler.filename}"'

        r.StaticFileHandler.status_code = 206 if r.StaticFileHandler.range_header else 200
        
        r.StaticFileHandler.reason = "Partial Content" if r.StaticFileHandler.status_code == 206 else "OK"
        
        r.StaticFileHandler.headers.update({
            "Accept-Ranges": "bytes",
            "Content-Type": r.StaticFileHandler.content_type,
            "Content-Disposition": r.StaticFileHandler.content_disposition,
            "Content-Length": r.StaticFileHandler.content_length,
        })

        if r.StaticFileHandler.range_header:
            r.StaticFileHandler.headers.update(
                {
                    "Content-Range": f'bytes {r.StaticFileHandler.start}-{r.StaticFileHandler.end}/{r.StaticFileHandler.file_size}'
                }
            )

    @classmethod
    async def serve_file(app, r, file_path, headers={}, CHUNK_SIZE=1024):
        await StaticFileHandler.prepare(r, file_path, headers, CHUNK_SIZE)

        await Stream.init(r, r.StaticFileHandler.headers, status=r.StaticFileHandler.status_code, reason=r.StaticFileHandler.reason)

        async with iopen(r.StaticFileHandler.file_path, mode="rb") as file:
            if r.StaticFileHandler.range_header:
                await file.seek(r.StaticFileHandler.start)

            while True:
                try:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    await Stream.write(r, chunk)
                except Abort as e:
                    await Log.m(r, e)
                    raise e
                    break
                except Err as e:
                    await Log.m(r, e)
                    raise e
                    break
                except Exception as e:
                    await Log.m(r, e)
                    break

    @classmethod
    async def stream_file(app, r, file_path, headers={}, CHUNK_SIZE=1024, prepared=False):
        if not prepared:
            await StaticFileHandler.prepare(r, file_path, headers, CHUNK_SIZE)

        await Stream.init(r, r.StaticFileHandler.headers, status=r.StaticFileHandler.status_code, reason=r.StaticFileHandler.reason)

        async with iopen(file_path, mode="rb") as file:
            if r.StaticFileHandler.range_header:
                await file.seek(r.StaticFileHandler.start)

            while True:
                try:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    yield chunk
                except Abort as e:
                    await Log.m(r, e)
                    raise e
                    break
                except Err as e:
                    await Log.m(r, e)
                    raise e
                    break
                except Exception as e:
                    await Log.m(r, e)
                    break

class Smart_Static_Server:
    root = "./static"
    static_chunk_size = 1024
    static_compressed_chunk_size = 1024 * 1024
    cache = {
        
    }

    compressable = [
        "text/html",
        "text/css",
        "text/javascript",
        "application/javascript",
        "application/x-javascript",
        "application/json",
        "application/xml", 
        "text/xml",
        "application/xhtml+xml",
        "image/svg+xml",
        "text/plain", 
        "text/markdown",
        "application/x-yaml",
        "text/yaml",
        "application/x-toml",
        "text/toml",
    ]
    
    @classmethod
    async def attach(app, parent):
        app = app()
        app.__dict__.update(parent.__dict__)
        parent.handle_all_middleware = app.handle_all_middleware
        return app

    async def is_compressable(app, r):
        if r.StaticFileHandler.content_type in app.compressable: return True

    async def handle_all_middleware(app, r):
        route = str(r.path)[1:]
        
        if route == "": route = "index"

        if not "." in route: route += ".html"
            
        file = join(app.root, route)
        headers = {}

        if file in app.cache:
            CachedStaticFileHandler = app.cache[file]["StaticFileHandler"]
            
            # Keeping up with latest versions of files
            if CachedStaticFileHandler.file_size != getsize(file):
                del app.cache[file]
            else:
                await Stream.init(r, CachedStaticFileHandler.headers, status=CachedStaticFileHandler.status_code, reason=CachedStaticFileHandler.reason)
                
                for chunk in app.cache[file]["chunks"]:
                    await Stream.write(r, chunk)
    
                return

        await StaticFileHandler.prepare(r, file, headers)
        
        should_compress = await app.is_compressable(r)

        if "gzip" in r.headers.get("Accept-Encoding", ""):
            if should_compress:
                should_compress = "gzip"

        elif "br" in r.headers.get("Accept-Encoding", ""):
            if should_compress:
                should_compress = False # NotImplemented
   
        if should_compress:
            chunk_size = app.static_compressed_chunk_size
            headers["Content-Encoding"] = str(should_compress)
        else:
            chunk_size = app.static_chunk_size

        async for chunk in StaticFileHandler.stream_file(r, file, CHUNK_SIZE=chunk_size, prepared=True):

            if not file in app.cache:
                app.cache[file] = {
                    "chunks": [],
                    "StaticFileHandler": r.StaticFileHandler
                }

            if should_compress and should_compress == "gzip":
                chunk = await to_thread(gzip_compress, chunk)

            app.cache[file]["chunks"].append(chunk)
            await Stream.write(r, chunk)


if __name__ == "__main__":
    pass
