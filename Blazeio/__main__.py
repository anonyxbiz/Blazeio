# Blazeio.__main__.py
from argparse import ArgumentParser
from .Client import Session
from .Dependencies import get_event_loop, log
from os import name

parser = ArgumentParser(prog="Blazeio", description="Blazeio")
parser.add_argument('url', type=str)

args = parser.parse_args()

class App:
    def __init__(app):
        pass

    async def fetch(app, url: str):
        if not "://" in url:
            url = "https://%s" % url

        async with Session(url, "GET", {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'accept-encoding': 'gzip, br',
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
        }) as r:
            async for chunk in r.pull():
                await log.info(chunk.decode())

def main():
    get_event_loop().run_until_complete(App().fetch(**args.__dict__))

if __name__ == "__main__":
    main()