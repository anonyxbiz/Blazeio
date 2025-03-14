from ..Dependencies import *
from .server_tools import Simpleserve

class TemplateEngine:
    __slots__ = ("static_path", "homepage", "html_path", "title", "description", "chunk_size", "cache_control", "template",)

    def __init__ (app, static_path = "./static", homepage = "/index", html_path = "page", description = "", title = "", chunk_size = 1024, cache_control={"max-age": "0"}, template = "page/tmpl.html",):

        for method, value in locals().items():
            if method not in app.__slots__: continue

            setattr(app, method, value)

    async def ayield(app, data):
        if not isinstance(data, str): data = str(data)
        data = escape(data)
        yield data.encode()

    async def date(app, r, ctx):
        data = escape(str(dt.now().year))
        yield data.encode()

    async def templatify(app, r, ctx, chunk, metadata, appctx = None):
        start, end, method, rmethod = b"<!--", b"-->", b"app.", b"r."

        while (ida := chunk.find(start)) != -1 and (idb := chunk.find(end)) != -1:
            var = chunk[ida + len(start):idb]

            yield chunk[:ida]
            chunk = chunk[idb + len(end):]

            if (idx := var.find(method)) != -1:
                var = var[idx + len(method):].decode("utf-8")
                
                appctx = appctx or app
                if hasattr(appctx, var) and callable(getattr(appctx, var)):
                    async for i in getattr(appctx, var)(r, ctx): yield i

            elif (idx := var.find(rmethod)) != -1:
                var = var[idx + len(rmethod):].decode("utf-8")
                if not "." in var: var += "."
                var = var.split(".")
                scope = None

                while var:
                    await sleep(0)
                    if not (x := var.pop(0)): break

                    if scope is None:
                        if hasattr(r, x):
                            scope = getattr(r, x)
                    else:
                        if isinstance(scope, dict):
                            scope = scope.get(x)
                        else:
                            if hasattr(scope, x):
                                scope = getattr(scope, x)

                if not isinstance(scope, str): scope = str(scope)

                yield escape(scope).encode()

            else:
                if (value := metadata.get(var)):
                    async for i in value[0](*value[1:]): yield i

        yield chunk

    async def handle_all_middleware(app, r, ctx = None, template = None, appctx = None):
        if r.path == "/": r.path = app.homepage
        if not "." in r.path: r.path = "/%s/%s.html" % (app.html_path, r.path)

        file = path.join(app.static_path, r.path[1:])
        
        if not ctx:
            ctx = Simpleserve()
            if not file.endswith(".html"): return await ctx.push(r, file, app.chunk_size, gzip=False)
    
            await ctx.initialize(r, file, app.chunk_size, cache_control=app.cache_control)
    
            for q in ("Content-Length", "Etag", "Cache-Control", "Last-Modified"): ctx.headers.pop(q, None)

        template_ctx = Simpleserve()

        await template_ctx.initialize(r, path.join(app.static_path, template or app.template), app.chunk_size, cache_control=app.cache_control)

        ctx.headers["Transfer-Encoding"] = "chunked"
        await r.prepare(ctx.headers, 200)

        metadata = {
            b'title': (app.ayield,ctx.filename[:ctx.filename.rfind(".")].capitalize()),
            b'app_title': (app.ayield, app.title),
            b'main': (ctx.pull,),
            b'description': (app.ayield, app.description)
        }

        async for chunk0 in template_ctx.pull():
            async for chunk1 in app.templatify(r, ctx, chunk0, metadata, appctx):
                async for chunk2 in app.templatify(r, ctx, chunk1, metadata, appctx):
                    await r.write_chunked(chunk2)

        await r.write_chunked_eof()
