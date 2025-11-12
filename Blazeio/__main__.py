# Blazeio.__main__.py
from .Dependencies.alts import *
from .Client import getSession
from os import name
from .Other.class_parser import Positional, Parser

class App:
    __slots__ = ("urls", "method", "save", "write", "headers", "slice_logs", "follow_redirects")
    def __init__(app, urls: (str, Utype, Positional) = None, method: (str, Utype) = "get", save: (str, Utype, None) = None, write: (str, Utype, None) = None, headers: (str, Utype, None) = None, slice_logs: (int, Utype) = 0, follow_redirects: (bool, Utype) = True):
        set_from_args(app, locals(), Utype)

    def default_headers(app, url, h):
        headers = { 'accept': '*/*', 'accept-language': 'en-US,en;q=0.9', 'accept-encoding': 'gzip, br', 'origin': url, 'priority': 'u=1, i', 'referer': url, 'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"%s"' % name.capitalize(), 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'BlazeI/O', 'connection': 'keep-alive', }
        if h: headers.update(h)
        return headers
    
    async def run(app):
        async with Ehandler():
            for url in app.urls.split(","):
                await app.fetch(url)

    async def fetch(app, url: str):
        if not url[:5].lower().startswith("http"): url = "https://%s" % url

        headers = app.default_headers(url, {header.split("=")[0]: header.split("=")[1] for header in app.headers.split(",") if "=" in header} if app.headers else app.headers)

        async with perf_timing() as timer:
            async with getSession(url, app.method or "get", headers, follow_redirects = app.follow_redirects) as resp:
                if app.save:
                    await resp.save(app.save)
                elif app.write:
                    if not resp.is_prepared(): await resp.prepare_http()

                    buff, filename, fd = bytearray(), None, None
                    if (ext := "html") in resp.content_type.lower():
                        title_s, title_e, title = b"<title", b"</title", None
    
                        async for chunk in resp:
                            if not fd: buff.extend(chunk)
                            if not fd and (idx := buff.find(title_s)) != -1:
                                title = (title := buff[idx + len(title_s) + 1:])[:title.find(title_e)].decode()
                                filename = title + ".%s" % ext
                                fd = await async_open(filename, "wb").__aenter__()
                                await fd.write(bytes(buff))
                            elif fd:
                                await fd.write(chunk)
                else:
                    async for chunk in resp:
                        try: chunk = chunk.decode()
                        except: ...

                        await log.info(chunk if not app.slice_logs else chunk[:app.slice_logs])

        await plog.blue("<%s@%s%s> completed request" % (resp.args[1].lower(), resp.host, resp.path), anydumps(ddict(request = ddict(host = resp.host, path = resp.path, headers = resp.headers, status_code = resp.status_code), metrics=timer.get())))

def main():
    ioConf.run(App(**Parser(App, Utype).args()).run())

if __name__ == "__main__":
    main()