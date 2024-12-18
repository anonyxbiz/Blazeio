# Blazeio.IN_MEMORY_STATIC_CACHE
from gzip import compress as gzip_compress
from os import path
from aiofiles import open as iopen
from mimetypes import guess_type
from asyncio import to_thread, create_task
from .streaming import Stream, Abort
from ..Dependencies import p, Err, Packdata

class IN_MEMORY_STATIC_CACHE:
    home_dir = None
    chunk_size = 1024
    caching = True
    cache = {}

    compress_for = [
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

    run_time_cache = {}

    @classmethod
    async def init(app, **kwargs):
        app = app()
        app.__dict__.update(**kwargs)
        await app.setup()

        return app

    async def setup(app):
        for route, item in app.run_time_cache.items():
            if path.exists((file_path := path.join(app.home_dir, "static", route))):
                await app.add_to_cache(file_path, item)

    async def compressed_chunk(app, file_data):
        chunk = b"".join(file_data["raw_chunks"])

        compressed = await to_thread(gzip_compress, chunk)
        
        file_data["compressed_chunks"] = [compressed]

    async def add_to_cache(app, file_path, item):
        file_data = {
            "headers": {},
            "path": file_path,
            "raw_chunks": None,
            "compressed_chunks": None
        }

        file_data["headers"]["Content-Length"] = (size := path.getsize(file_path))
        file_data["headers"]["Content-Type"] = guess_type(file_path)[0]
        file_data["headers"]["Content-Disposition"] = f'inline; filename="{(filename := path.basename(file_path))}"'

        if not (route_ := item.get("route")):
            route = "/%s" % filename
        else:
            route = route_

        app.cache[route] = file_data

    async def serve(app, r, route: str):
        file_data = app.cache.get(route)
        headers = {a:b for a,b in file_data["headers"].items()}
    
        is_being_cached = False

        if app.caching and file_data["headers"]["Content-Length"] == path.getsize(file_data["path"]) and file_data["raw_chunks"]:
            is_being_cached = True
            chunked_data = None

            if file_data["compressed_chunks"] and "gzip" in r.headers.get("Accept-Encoding", ""):
                chunked_data = await Packdata.add(**{"type": "compressed_chunks", "data": file_data["compressed_chunks"]})
                headers["Content-Encoding"] = "gzip"

            elif file_data["raw_chunks"]:
                chunked_data = await Packdata.add(**{"type": "raw_chunks", "data": file_data["raw_chunks"]})

            if chunked_data:
                end = len(chunked_data.data)
                cur = 0

                # Prepare response
                await Stream.init(r, headers, status=206)
    
                while True:
                    chunk = chunked_data.data[cur]
                    await Stream.write(r, chunk)
                    cur += 1
    
                    if cur >= end: break

        if is_being_cached:
            return

        file_data["headers"]["Content-Length"] = path.getsize(file_data["path"])

        async with iopen(file_data["path"], mode="rb") as f:
            if app.caching:
                file_data["raw_chunks"] = []

            # Prepare response
            await Stream.init(r, headers, status=206)

            while True:
                try:
                    chunk = await f.read(app.chunk_size)
                    if not chunk: break
                    await Stream.write(r, chunk)
                    if app.caching: file_data["raw_chunks"].append(chunk)

                except Exception as e:
                    p(e)
                    # Reset chunks since this is incomplete
                    file_data["raw_chunks"] = None
                    raise e
            
            if app.caching:
                if file_data["headers"]["Content-Type"] in app.compress_for:
                    task = create_task(app.compressed_chunk(file_data))

    # all routes
    async def handler(app, r, override="/"):
        route = r.path

        if not route in app.cache:
            route, item = route, {"route": route}
            if (i := "/") in route:
                route = i.join(route.split(i)[1:])
    
            if path.exists((file_path := path.join(app.home_dir, "static", route))):
                await app.add_to_cache(file_path, item)
            else:
                raise Abort("The Content you\"re looking for, cannot be found", 404)

        try:
            await app.serve(r, r.path)
        except Exception as e:
            p(e)
            return

if __name__ == "__main__":
    pass