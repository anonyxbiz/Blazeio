from ..Dependencies import *
from ..Dependencies import *
from .request import *
from .streaming import *

class StaticFileHandler:
    CHUNK_SIZE = 1024

    @classmethod
    async def prepare(app, r: Packdata, file_path, headers={}, CHUNK_SIZE=None):

        if not exists(file_path):
            raise Abort("File Not Found", 404, reason="Not Found")

        r.StaticFileHandler = await Packdata.add(file_path=file_path, headers=headers, CHUNK_SIZE=CHUNK_SIZE or app.CHUNK_SIZE)

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

        r.StaticFileHandler.status_code = 206 if r.StaticFileHandler.range_header else 206
        
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
    async def prepare_static(app, r, file_path, headers={}, CHUNK_SIZE=None):
        if not exists(file_path): raise Abort("File Not Found", 404, reason="Not Found")
        
        content_type, _ = guess_type(file_path)
        filename = file_path.split("/")[-1]
        content_disposition = f'inline; filename="{filename}"'

        file_size = getsize(file_path)

        if range_header := r.headers.get('Range'):
            range_header = range_header
            byte_range = range_header.strip().split('=')[1]
            start, end = byte_range.split('-')
            start = int(start)
            end = int(end) if end else file_size - 1
        else:
            range_header = None
            start, end = 0, file_size

        content_length = file_size

        if not content_type:
            content_type = "application/octet-stream"
            content_disposition = f'attachment; filename="{filename}"'

        status_code = 206# if range_header else 200
        
        reason = "Partial Content" if status_code == 206 else "OK"
        
        headers.update({
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
            "Content-Disposition": content_disposition,
            #"Content-Length": content_length,
        })

        if range_header: headers["Content-Range"] = f'bytes {start}-{end}/{file_size}'
        else: start = 0
        
        return headers, status_code, reason, range_header, start, end

    @classmethod
    async def serve_file(app, r, file_path, headers={}, CHUNK_SIZE=None):
        headers, status_code, reason, range_header, start, end = await app.prepare_static(r, file_path, headers, CHUNK_SIZE)

        await Stream.init(r, headers, status=status_code, reason=reason)

        async with iopen(file_path, mode="rb") as file:
            while True:
                file.seek(start)

                if not (chunk := await file.read(CHUNK_SIZE)):
                    break
                else:
                    start += len(chunk)

                await r.write(chunk)
                #await r.control()
                #if start >= end: break

    @classmethod
    async def stream_file(app, r, file_path, headers={}, CHUNK_SIZE=1024, prepared=False):
        headers, status_code, reason, range_header, start, end = await app.prepare_static(r, file_path, headers, CHUNK_SIZE)
        
        if "Content-Length" in headers:
            del headers["Content-Length"]
        
        await Stream.init(r, headers, status=status_code, reason=reason)
        
        async with iopen(file_path, mode="rb") as file:
            while True:
                file.seek(start)

                if not (chunk := await file.read(length = CHUNK_SIZE)):
                    break
                else:
                    start += len(chunk)

                yield chunk
                await sleep(0)

class Staticwielder:
    async def __aenter__(app):
        return app
    
    async def stream_file(app, *args, **kwargs):
        async for chunk in StaticFileHandler.stream_file(*args, **kwargs):
            yield chunk
    
    async def __aexit__(app, ext_type, ext, tb):
        pass

class Smart_Static_Server:
    async def attach(app, parent):
        app.root = "./static"
        app.static_chunk_size = 1024
        app.max_cachable_file_size = 1024
        app.static_compressed_chunk_size = 1024 * 1024
        app.cache_aliveness = float(60)
        app.cache_check_interval = 60
        app.watching = False
        app.cache = {}
    
        app.compressable = [
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
        
        app.__dict__.update(parent.__dict__)
        
        parent.handle_all_middleware = app.handle_all_middleware

        loop.create_task(app.cache_watch())
        return app

    async def cache_watch(app):
        while True:
            if app.cache != {}:
                remove = []
                
                for file, metadata in app.cache.items():
                    duration = dt.now().timestamp() - metadata["StaticFileHandler"].analytics["last_hit"]

                    if duration >= app.cache_aliveness:
                        remove.append(file)
                
                if remove != []:
                    for file in remove: del app.cache[file]
    
            await sleep(app.cache_check_interval)

    async def is_compressable(app, r):
        if r.StaticFileHandler.content_type in app.compressable: return True

    async def handle_all_middleware(app, r):
        route = str(r.path)[1:]
        
        if route == "": route = "index"

        if not "." in route: route += ".html"
            
        file = join(app.root, route)
        headers = {}

        if file in app.cache and app.cache[file]["chunks"]:
            CachedStaticFileHandler = app.cache[file]["StaticFileHandler"]
            
            # Keeping up with latest versions of files
            if CachedStaticFileHandler.file_size != getsize(file):
                del app.cache[file]
            else:
                CachedStaticFileHandler.analytics["last_hit"] = dt.now().timestamp()
                CachedStaticFileHandler.analytics["hits"] += 1

                await Stream.init(r, CachedStaticFileHandler.headers, status=CachedStaticFileHandler.status_code, reason=CachedStaticFileHandler.reason)
                
                for chunk in app.cache[file]["chunks"]:
                    await Stream.write(r, chunk)

                return

        await StaticFileHandler.prepare(r, file, headers)
        
        should_compress = await app.is_compressable(r)
        should_cache = True
        
        if r.StaticFileHandler.file_size >= app.max_cachable_file_size:
            should_cache = False

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
                
                r.StaticFileHandler.analytics = {
                    "last_hit": dt.now().timestamp(),
                    "hits": 1,
                    "added": dt.now().timestamp(),
                    "added_time": str(dt.now().time()).split(".")[0]
                }
            else:
                app.cache[file]["StaticFileHandler"].analytics["last_hit"] = dt.now().timestamp()
                app.cache[file]["StaticFileHandler"].analytics["hits"] += 1

            if should_compress and should_compress == "gzip":
                chunk = await to_thread(gzip_compress, chunk)

            if should_cache: app.cache[file]["chunks"].append(chunk)
            
            try:
                await Stream.write(r, chunk)
            except Exception as e:
                p(e)

if __name__ == "__main__":
    pass
