import Blazeio as io
from os import mkdir, access as os_access, R_OK as os_R_OK, W_OK as os_W_OK, X_OK as os_X_OK, makedirs
from pathlib import Path

scope = io.DotDict()

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*100, 1024*100

class Pathops:
    __slots__ = ("parent",)
    parent_dir = "Blazeio_Other_proxy"

    def __init__(app):
        root = Path.cwd().resolve()
        while root.parent != root:
            readable = os_access(root.parent, os_R_OK)
            writable = os_access(root.parent, os_W_OK)
            executable = os_access(root.parent, os_X_OK)

            if not all([readable, writable, executable]): break

            root = root.parent

        app.parent = io.path.join(root, app.parent_dir)

        makedirs(app.parent, exist_ok=True)

HOME = Pathops().parent

class Sslproxy:
    __slots__ = ()
    ssl_configs = {"certfile": "proxytest.cert", "keyfile": "proxytest.pem"}
    cert_dir = io.path.join(HOME, "cert_dir")
    
    makedirs(cert_dir, exist_ok=True)

    ssl_contexts = {}

    def __init__(app): pass

    def sni_callback(app, ssl_socket, server_name, ssl_context):
        if not server_name:
            server_name = "hook.localhost"

        if server_name and (server := app.hosts.get(server_name)) is not None:
            if not (ctx := server.get("ssl_context")) or not (ctx := app.ssl_contexts.get(ctx)):
                if not all([(certfile := server.get("certfile")), (keyfile := server.get("keyfile"))]) or not all([io.path.exists(certfile), io.path.exists(keyfile)]):
                    if certfile and not io.path.exists(certfile):
                        certfile = io.path.join(app.cert_dir, certfile)

                    if keyfile and not io.path.exists(keyfile):
                        keyfile = io.path.join(app.cert_dir, keyfile)
                    
                    if not certfile and not keyfile:
                        certfile, keyfile = io.path.join(app.cert_dir, server_name + ".cert"), io.path.join(app.cert_dir, server_name + ".pem")

                    scope.web.setup_ssl(server_name, None, ssl_data := dict(certfile=certfile, keyfile=keyfile), setup=False)

                    server.update(ssl_data)

                ctx = io.create_default_context(io.Purpose.CLIENT_AUTH)
                ctx.load_cert_chain(certfile, keyfile)

                ctx.options |= io.OP_NO_COMPRESSION
                ctx.set_ecdh_curve('prime256v1')
                # ctx.post_handshake_auth = False

                app.ssl_contexts[server_name] = ctx
                server["ssl_context"] = server_name

            ssl_socket.context = ctx
            ssl_socket.context.server_hostname = server_name

    def configure_ssl(app):
        context = io.create_default_context(io.Purpose.CLIENT_AUTH)
    
        context.sni_callback = app.sni_callback

        # context.post_handshake_auth = False
        context.options |= io.OP_NO_COMPRESSION
        context.set_ecdh_curve('prime256v1')
        
        return context

class Transporters:
    __slots__ = ()
    tls_record_size = 256

    def __init__(app): pass

    async def puller(app, r, resp):
        async for chunk in r.pull():
            await resp.write(chunk)

        await resp.eof()

    async def no_tls_transporter(app, r: io.BlazeioProtocol, remote: str, srv: dict):
        task = None
        async with io.Session(remote + r.tail, r.method, r.headers, decode_resp=False, add_host = False) as resp:
            if r.method not in r.non_bodied_methods:
                task = io.create_task(app.puller(r, resp))

            await resp.prepare_http()

            await r.prepare(resp.headers, resp.status_code, encode_resp=False)

            async for chunk in resp.pull():
                await r.write(chunk)

            await r.eof()

            if task: await task

    async def tls_transporter(app, r: io.BlazeioProtocol, remote: str, srv: dict):
        task = None
        async with io.Session(remote + r.tail, r.method, r.headers, decode_resp=False, add_host = False) as resp:
            if r.method not in r.non_bodied_methods:
                task = io.create_task(app.puller(r, resp))

            if not resp.is_prepared():
                await resp.prepare_http()

            await r.prepare(resp.response_headers, resp.status_code, encode_resp=False)
            
            buff = bytearray()

            async for chunk in resp.pull():
                if not buff and len(chunk) >= app.tls_record_size:
                    await r.write(chunk)
                    continue
                
                buff.extend(chunk)

                if len(buff) >= app.tls_record_size:
                    _, buff = await r.write(buff), buff[len(buff):]
                else:
                    continue

            await r.eof(buff)

            if task: await task

class App(Sslproxy, Transporters):
    __slots__ = ("hosts", "tasks", "protocols", "protocol_count", "host_update_event", "protocol_update_event", "timeout", "blazeio_proxy_hosts", "log", "transporter",)

    def __init__(app, blazeio_proxy_hosts: str = "blazeio_proxy_hosts.txt", timeout: float = float(60*10), log: bool = False, proxy_port = None):
        app.blazeio_proxy_hosts = io.path.join(HOME, blazeio_proxy_hosts)
        app.hosts = {
            "hook.localhost": {},
        }

        app.tasks = []
        app.log = log
        app.transporter = app.no_tls_transporter
        app.protocols = {}
        app.protocol_count = 0
        app.host_update_event = io.SharpEvent(True, io.ioConf.loop)
        app.protocol_update_event = io.SharpEvent(True, io.ioConf.loop)
        app.timeout = timeout

        app.tasks.append(io.ioConf.loop.create_task(app.update_file_db()))
        app.tasks.append(io.ioConf.loop.create_task(app.update_mem_db()))
        app.tasks.append(io.ioConf.loop.create_task(app.protocol_manager()))
    
    def to_dict(app):
        data = {}
        for key in app.__slots__:
            val = getattr(app, key)
            if not isinstance(val, (str, int, dict)):
                val = str(val)
            
            data[str(key)] = val
        
        return data

    async def update_file_db(app):
        while await app.host_update_event.wait():
            async with io.async_open(app.blazeio_proxy_hosts, "wb") as f:
                await f.write(io.dumps(app.hosts).encode())

    async def update_mem_db(app):
        if not io.path.exists(app.blazeio_proxy_hosts): return

        async with io.async_open(app.blazeio_proxy_hosts, "rb") as f:
            app.hosts.update(io.loads(await f.read()))

        await io.plog.cyan("update_mem_db", "loaded: %s" % io.dumps(app.hosts, indent=1))

    async def remote_webhook(app, r):
        json = await io.Request.get_json(r)

        app.hosts.update(json)
        app.host_update_event.set()

        await io.plog.cyan("remote_webhook", "added: %s" % io.dumps(app.hosts, indent=1))

        raise io.Abort("Added", 200)

    async def logger(app, r, i):
        await io.plog.cyan("%s:%d | %s@%s%s" % (r.ip_host, r.ip_port, r.method.upper(), i[-1], r.tail), ", ".join(["(%s=%s)" % (i, str(getattr(r, i, ""))[:100]) for i in r.__slots__]))

    async def protocol_manager(app, run = False):
        if not run:
            while await app.protocol_update_event.wait():
                await app.protocol_manager(True)
            return

        for i in app.protocols:
            if not (r := app.protocols.get(i)): continue

            if app.log: await app.logger(r, i)

            if (elapsed := float(io.perf_counter() - r.__perf_counter__)) >= app.timeout:
                r.cancel(str(io.Protocoltimeout()))
                app.protocols.pop(r.identifier)

    # Blazeio callback for a custom protocol
    async def __main_handler__(app, r: io.BlazeioProtocol):
        await io.Request.prepare_http_request(r)
        
        host = r.headers.get("Host", "")

        if "Remote_webhook" in r.headers:
            if r.ip_host != "127.0.0.1":
                raise io.Abort("Server could not be found", 503) # return generic response

            return await getattr(app, r.headers.get("route", "remote_webhook"))(r)
        
        if (idx := host.rfind(":")) != -1:
            host = host[:idx]

        if not (srv := app.hosts.get(host)) or not (remote := srv.get("remote")):
            raise io.Abort("Server could not be found", 503)
        
        r.headers["ip_host"] = str(r.ip_host)
        r.headers["ip_port"] = str(r.ip_port)
        r.headers["Original_host"] = host
        r.headers["ip_port"] = str(r.ip_port)

        app.protocol_count += 1
        r.identifier = (app.protocol_count, remote)
        r.__perf_counter__ = io.perf_counter()

        try:
            app.protocols[r.identifier] = r
            app.protocol_update_event.set()
            await app.transporter(r, remote, srv)
        finally:
            app.protocols.pop(r.identifier)

class WebhookClient:
    __slots__ = ("conf",)
    def __init__(app):
        app.conf = io.path.join(HOME, "conf.txt")

    def save_state(app, data: dict):
        with open(app.conf, "wb") as f:
            f.write(io.dumps(data, indent=1).encode())

    def get_state(app):
        with open(app.conf, "rb") as f:
            return io.loads(f.read())

    async def add_to_proxy(app, host, port, certfile = None, keyfile = None, in_try = False, **kw):
        if not in_try:
            try:
                return await app.add_to_proxy(host, port, certfile, keyfile, in_try = True, **kw)
            except Exception as e:
                return await io.traceback_logger(e)

        if (idx := host.rfind(":")) != -1:
            host = host[:idx]

        state = app.get_state()

        async with io.Session.post("http://127.0.0.1:%d/" % int(state.get("Blazeio.Other.proxy.port")), {"Remote_webhook": "Remote_webhook", "Content-type": "application/json", "Transfer-encoding": "chunked", "route": "remote_webhook"}, ssl = io.ssl_context if state.get("Blazeio.Other.proxy.ssl") else None) as session:
            await session.eof(io.dumps({
                host: {
                    "remote": "http://localhost:%d" % port,
                    "certfile": certfile,
                    "keyfile": keyfile
                    
                }
            }).encode())

            await io.plog.cyan("Proxy.add_to_proxy", await session.text())

whclient = WebhookClient()

add_to_proxy = lambda *a, **k: io.ioConf.run(whclient.add_to_proxy(*a, **k))

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-port", "--port", default = 8080)
    parser.add_argument("-ssl", "--ssl", default = False)

    args = parser.parse_args()

    scope.web = io.App("0.0.0.0", proxy_port := int(args.port), __log_requests__=0)

    scope.web.attach(app := App(proxy_port = proxy_port))

    if args.ssl:
        app.transporter = app.tls_transporter
        conf = dict(ssl=app.configure_ssl())
    else:
        conf = dict()
    
    state = app.to_dict()
    
    state.update({
        "Blazeio.Other.proxy.port": proxy_port,
        "Blazeio.Other.proxy.ssl": args.ssl
    })

    whclient.save_state(state)

    scope.web.runner(**conf)
