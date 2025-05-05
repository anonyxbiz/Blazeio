# Blazeio.__main__.py
from argparse import ArgumentParser
from .Dependencies import *
from .Client import Session
from os import name

ioConf.OUTBOUND_CHUNK_SIZE = 4096

parser = ArgumentParser(prog="Blazeio", description = "Blazeio is a cutting-edge asynchronous web server and client framework designed for building high-performance backend applications with minimal overhead.")

parser.add_argument('url', type=str)

for query, _type, _help in (("save", str, "filepath"), ("method", str, "http request method")):
    parser.add_argument('-%s' % query, '--%s' % query, type = _type, required = False, help = _help.capitalize())

args = parser.parse_args()

class App:
    def __init__(app): pass

    async def fetch(app, url: str, method: (None, str) = None, save: (None, str) = None):
        if "," in url:
            return [await app.fetch(i, method, save) for i in url.split(",")]

        if not url[:5].lower().startswith("http"): url = "https://%s" % url

        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'origin': url,
            'priority': 'u=1, i',
            'referer': url,
            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"%s"' % name.capitalize(),
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'BlazeI/O',
            'connection': 'keep-alive',
        }
        
        start = perf_counter()
        async with Session(url, method or "get", headers, follow_redirects = True) as resp:
            if save:
                await resp.save(save)
            else:
                async for chunk in resp.pull():
                    await log.info(chunk.decode())

            await log.debug("<%s@%s%s> completed request in <%s's>." % (resp.args[1].lower(), resp.host, resp.path, str(perf_counter() - start)))

def main():
    loop.run_until_complete(App().fetch(**args.__dict__))

if __name__ == "__main__":
    main()