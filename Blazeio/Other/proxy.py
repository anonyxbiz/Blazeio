import Blazeio as io
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-port", "--port", default = 8080)
args = parser.parse_args()

web = io.App("0.0.0.0", int(args.port), __log_requests__=0)

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*100, 1024*100

class App:
    hosts = {}

    def __init__(app):
        pass

    async def puller(app, r, resp):
        async for chunk in r.pull():
            await resp.write(chunk)
        
        await resp.eof()
    
    async def add_host(app, r):
        host, srv = (json := await io.Request.get_json(r)).get("host"), json.get("srv")

        json = {host + ":%d" % web.ServerConfig.port: srv}

        app.hosts.update(json)

        raise io.Abort("Added", 200)

    async def __main_handler__(app, r):
        await io.Request.prepare_http_request(r)
        
        if (host := r.headers.get("Host", "")).startswith("localhost") and r.tail == "/$add_host":
            if r.ip_host != "127.0.0.1":
                raise io.Abort("Server could not be found", 503) # return generic response

            return await app.add_host(r)

        if not (remote := app.hosts.get(host)):
            raise io.Abort("Server could not be found", 503)

        tasks = []
        async with io.Session(remote + r.tail, r.method, r.headers, decode_resp=False) as resp:
            if r.method not in r.non_bodied_methods:
                tasks.append(io.create_task(app.puller(r, resp)))

            await resp.prepare_http()

            await r.prepare(resp.headers, resp.status_code, encode_resp=False)

            async for chunk in resp.pull():
                await r.write(chunk)

            await r.eof()

            if tasks: await io.gather(*tasks)

async def add_to_proxy(host = "test.localhost", port = web.ServerConfig.port):
    try:
        async with io.Session("http://localhost:8080/$add_host", "post", io.Rvtools.headers, json = {"host": host, "srv": "http://localhost:%d" % port}) as session:
            await session.aread(1)
    except:
        pass
        
if __name__ == "__main__":
    web.attach(App())
    web.runner()