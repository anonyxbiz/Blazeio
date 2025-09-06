# Blazeio.__main__.py
from argparse import ArgumentParser
from .Dependencies.alts import *
from .Client import Session, getSession
from os import name

class App:
    def __init__(app): ...
    
    def default_headers(app, url, h):
        headers = { 'accept': '*/*', 'accept-language': 'en-US,en;q=0.9', 'accept-encoding': 'gzip, br', 'origin': url, 'priority': 'u=1, i', 'referer': url, 'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"%s"' % name.capitalize(), 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'BlazeI/O', 'connection': 'keep-alive', }
        if h: headers.update(h)
        return headers

    async def fetch(app, url: (Utype, True, str) = "https://example.com", method: (Utype, None, None, str) = None, save: (Utype, None, str) = None, write: (Utype, None, str) = None, headers: (Utype, None, str) = None, slice_logs: (Utype, None, int) = 0):
        if not url[:5].lower().startswith("http"): url = "https://%s" % url

        headers = app.default_headers(url, {header.split("=")[0]: header.split("=")[1] for header in (headers + ",").split(",") if "=" in header} if headers else headers)

        async with perf_timing() as timer:
            async with getSession(url, method or "get", headers, follow_redirects = True) as resp:
                if save:
                    await resp.save(save)
                elif write:
                    if not resp.is_prepared(): await resp.prepare_http()

                    buff, filename, fd = bytearray(), None, None
                    if (ext := "html") in resp.content_type.lower():
                        title_s, title_e, title = b"<title", b"</title", None
    
                        async for chunk in resp.pull():
                            if not fd: buff.extend(chunk)
                            if not fd and (idx := buff.find(title_s)) != -1:
                                title = (title := buff[idx + len(title_s) + 1:])[:title.find(title_e)].decode()
                                filename = title + ".%s" % ext
                                fd = await async_open(filename, "wb").__aenter__()
                                await fd.write(bytes(buff))
                            elif fd:
                                await fd.write(chunk)
                else:
                    async for chunk in resp.pull():
                        try: chunk = chunk.decode()
                        except: ...

                        await log.info(chunk if not slice_logs else chunk[:slice_logs])

        await plog.debug("<%s@%s%s> completed request" % (resp.args[1].lower(), resp.host, resp.path), dumps(ddict(metrics=timer.get())))

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(prog="Blazeio", description = "Blazeio is a cutting-edge asynchronous web server and client framework designed for building high-performance backend applications with minimal overhead.")
    
    # parser.add_argument('url', type=str)

    for arg_count, arg in enumerate(App.fetch.__annotations__.keys()):
        arg_type = App.fetch.__annotations__.get(arg)
        if not isinstance(arg_type, tuple) or not Utype in arg_type: continue
        
        arg_data = ddict(arg = arg, required = arg_type[1], type = arg_type[2], default = App.fetch.__defaults__[arg_count])

        if arg_data.required:
            parser.add_argument(arg_data.arg, type = arg_data.type)
        else:
            parser.add_argument("-%s" % arg_data.arg, "--%s" % arg_data.arg, type = arg_data.type, default = arg_data.default)

    args = parser.parse_args()
    ioConf.run(App().fetch(**args.__dict__))

if __name__ == "__main__":
    main()