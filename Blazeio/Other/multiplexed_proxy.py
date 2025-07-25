import Blazeio as io
from os import mkdir, access as os_access, R_OK as os_R_OK, W_OK as os_W_OK, X_OK as os_X_OK, makedirs
from pathlib import Path
from ssl import TLSVersion
from Blazeio.Protocols.multiplexer import BlazeioClientProtocol, BlazeioServerProtocol

scope = io.Dot_Dict(
    tls_record_size = 256,
    server_name = "blazeio.other.multiplexed_proxy.localhost",
    parent_dir = "Blazeio_Other_Multiplexed_proxy",
    server_set = io.SharpEvent(False, io.loop),
)

class Pathops:
    __slots__ = ("parent",)
    def __init__(app):
        app.parent = io.path.abspath(io.path.join(io.environ.get('HOME'), scope.parent_dir))
        makedirs(app.parent, exist_ok=True)

scope.HOME = Pathops().parent

class Sslproxy:
    __slots__ = ()
    ssl_configs = {"certfile": "proxytest.cert", "keyfile": "proxytest.pem"}
    cert_dir = io.path.join(scope.HOME, "cert_dir")
    
    makedirs(cert_dir, exist_ok=True)

    ssl_contexts = {}

    def __init__(app): pass

    def sni_callback(app, ssl_socket, server_name, ssl_context):
        if not server_name:
            server_name = scope.server_name

        if (server := app.hosts.get(server_name)) is not None:
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

                ctx = app.context()

                ctx.load_cert_chain(certfile, keyfile)

                app.ssl_contexts[server_name] = ctx
                server["ssl_context"] = server_name

            ssl_socket.context = ctx
            ssl_socket.context.server_hostname = server_name
    
    def context(app):
        context = io.create_default_context(io.Purpose.CLIENT_AUTH)
        context.post_handshake_auth = False
        context.options |= io.OP_NO_COMPRESSION
        context.set_ecdh_curve("prime256v1")
        context.minimum_version = TLSVersion.TLSv1_3
        context.session_tickets = True
        return context

    def configure_ssl(app):
        context = app.context()
        context.sni_callback = app.sni_callback
        return context

class Transporters:
    __slots__ = ()
    __conn__ = io.ioCondition(evloop = io.loop)
    __serialize__ = io.ioCondition(evloop = io.loop)

    def __init__(app): pass

    async def puller(app, r, resp):
        async with resp.protocol:
            async for chunk in r.pull():
                await resp.writer(chunk)

    def prepare(app, r, headers, *args, **kwargs):
        headers = {key.capitalize(): val for key, val in headers.items()}

        headers.update({"Blazeio.other.proxy.protocol.telemetry.%s" % key: val for key, val in r.store.telemetry._dict.items()})

        if "Server" in headers:
            headers["Blazeio.other.proxy.protocol.remote.server"] = headers.pop("Server")

        return r.prepare(headers, *args, **kwargs)

    async def _conn(app, srv):
        async with app.__conn__:
            if not (conn := srv.get("conn")) or (not conn.protocol) or (conn.protocol.transport.is_closing()):
                srv["conn"] = (conn := await io.Session(srv.get("remote"), client_protocol = BlazeioClientProtocol, connect_only = 1).__aenter__())

        return conn.create_stream()

    async def conn(app, srv):
        try:
            return await app._conn(srv)
        except OSError:
            srv.pop("conn", False)
            raise io.Abort("Service Unavailable", 500)

    async def no_tls_transporter(app, r, srv: dict):
        r.store.telemetry.ttfb = lambda start = io.perf_counter(): (io.perf_counter() - start)
        async with io.Session(srv.get("remote") + r.tail, r.method, r.headers, decode_resp=False, add_host = False, use_protocol = await app.conn(srv)) as resp:
            r.store.telemetry.ttc = r.store.telemetry.ttfb()

            if r.method not in r.non_bodied_methods:
                r.store.task = io.create_task(app.puller(r, resp))
            else:
                await resp.__eof__()

            if not resp.is_prepared(): await resp.prepare_http()

            r.store.telemetry.ttfb = r.store.telemetry.ttfb()

            await app.prepare(r, resp.headers, resp.status_code, resp.reason_phrase, encode_resp = False)

            async for chunk in resp.__pull__():
                await r.writer(chunk)

            if r.store.task: await r.store.task
    
    async def __write_chunks__(app, r, chunk = b"", chunk_size = 1024):
        if r.store.buff or len(chunk) < scope.tls_record_size:
            if chunk:
                r.store.buff.extend(chunk)
                if len(r.store.buff) < scope.tls_record_size:
                    return
                else:
                    chunk = b""

            chunk = bytes(r.store.buff) + chunk
            r.store.buff.clear()

        while chunk and len(chunk) >= chunk_size:
            _, chunk = bytes(memoryview(chunk)[:chunk_size]), bytes(memoryview(chunk)[chunk_size:])
            await r.writer(_)

        if chunk:
            await r.writer(chunk)

    async def tls_transporter(app, r, srv: dict):
        r.store.telemetry.ttfb = lambda start = io.perf_counter(): (io.perf_counter() - start)

        async with io.Session(srv.get("remote") + r.tail, r.method, r.headers, decode_resp=False, add_host = False, use_protocol = await app.conn(srv)) as resp:
            r.store.telemetry.ttc = r.store.telemetry.ttfb()

            if r.method not in r.non_bodied_methods:
                r.store.task = io.create_task(app.puller(r, resp))
            else:
                async with resp.protocol: pass

            if not resp.is_prepared(): await resp.prepare_http()

            r.store.telemetry.ttfb = r.store.telemetry.ttfb()

            await app.prepare(r, resp.headers, resp.status_code, resp.reason_phrase, encode_resp = False)

            r.store.buff = bytearray()

            async for chunk in resp.__pull__():
                await app.__write_chunks__(r, chunk)

            await app.__write_chunks__(r)

            if r.store.task: await r.store.task

class App(Sslproxy, Transporters):
    __slots__ = ("hosts", "tasks", "protocols", "protocol_count", "host_update_cond", "protocol_update_event", "timeout", "blazeio_proxy_hosts", "log", "transporter", "track_metrics", "fresh")

    def __init__(app, blazeio_proxy_hosts = "blazeio_proxy_hosts_.txt", timeout = float(60*10), log = False, track_metrics = True, proxy_port = None, protocols = {}, protocol_count = 0, tasks = [], protocol_update_event = io.SharpEvent(True, io.ioConf.loop), host_update_cond = io.ioCondition(evloop = io.ioConf.loop), hosts = {scope.server_name: {}}, fresh: bool = False):
        for key in (__locals__ := locals()):
            if key not in app.__slots__: continue
            if getattr(app, key, NotImplemented) != NotImplemented: continue
            setattr(app, key, __locals__[key])

        app.blazeio_proxy_hosts = io.path.join(scope.HOME, blazeio_proxy_hosts)

        if app.log:
            io.loop.create_task(io.log.debug("blazeio_proxy_hosts: %s" % app.blazeio_proxy_hosts))

        app.transporter = app.no_tls_transporter

        app.tasks.append(io.ioConf.loop.create_task(app.update_mem_db()))
        app.tasks.append(io.ioConf.loop.create_task(app.protocol_manager()))
    
    def json(app):
        data = {}
        for key in app.__slots__:
            if not isinstance(val := getattr(app, key), (str, int, dict)):
                val = str(val)

            data[str(key)] = val
        
        return data

    async def update_file_db(app):
        async with app.host_update_cond:
            data = io.dumps({key: {a:b for a, b in val.items() if a not in ("conn",)} for key, val in app.hosts.items()}).encode()
            async with io.async_open(app.blazeio_proxy_hosts, "wb") as f:
                await f.write(data)

    async def update_mem_db(app):
        if not io.path.exists(app.blazeio_proxy_hosts) or app.fresh: return

        async with io.async_open(app.blazeio_proxy_hosts, "rb") as f:
            app.hosts.update(io.loads(await f.read()))

        await io.plog.cyan("update_mem_db", "loaded: %s" % io.dumps(app.hosts, indent=4, escape_forward_slashes = False))

    async def _remote_webhook(app, r):
        app.hosts.update(json := await io.Request.get_json(r))

        await app.update_file_db()

        await io.plog.cyan("remote_webhook", "added: %s" % io.dumps(json, indent=1))

        await io.Deliver.json(json)

    async def _discover(app, r):
        await io.Deliver.json({"discovered": True})

    async def _proxy_state(app, r):
        json = {}
        
        for key in app.__slots__:
            val = getattr(app, key, None)
            
            if not isinstance(val, (int, dict, str)):
                val = str(val)
                
            elif isinstance(val, dict):
                val = {k: str(v) if not isinstance(v, (int, str)) else v for k, v in val.items()}

            json[key] = val

        raise io.Eof(await io.Deliver.json(json))

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
    
    def is_from_home(app, r, host: str):
        if r.ip_host == "127.0.0.1":
            if host != scope.server_name: return False
        else:
            return False

        return True

    async def __main_handler__(app, r):
        # r.transport.set_write_buffer_limits(0)
        r.store = io.Dot_Dict()
        r.store.telemetry = io.Dot_Dict()

        app.protocol_count += 1
        r.identifier = app.protocol_count
        r.__perf_counter__ = io.perf_counter()

        r.store.telemetry.prepare_http_request = lambda start = io.perf_counter(): (io.perf_counter() - start)

        await io.Request.prepare_http_request(r)

        r.store.telemetry.prepare_http_request = r.store.telemetry.prepare_http_request()
        r.store.telemetry.host_derivation = lambda start = io.perf_counter(): (io.perf_counter() - start)

        host = r.headers.get("Host", "")
        if (idx := host.rfind(":")) != -1:
            host = host[:idx]

        r.store.telemetry.host_derivation = r.store.telemetry.host_derivation()

        if app.is_from_home(r, host):
            if not (route := getattr(app, r.headers.get("route", r.path.replace("/", "_")), None)):
                raise io.Abort("Not Found", 404)

            return await route(r)

        if not (srv := app.hosts.get(host)) or not (remote := srv.get("remote")):
            raise io.Abort("Server could not be found", 503)

        try:
            app.protocols[r.identifier] = r
            if not app.protocol_update_event.is_set(): app.protocol_update_event.set()
            await app.transporter(r, srv)
        finally:
            app.protocols.pop(r.identifier, None)
            if not app.protocol_update_event.is_set(): app.protocol_update_event.set()

class WebhookClient:
    __slots__ = ("conf", "availablity")
    def __init__(app):
        app.conf = io.path.join(scope.HOME, "conf")
        app.availablity = None

    def save_state(app, data: dict):
        with open(app.conf, "wb") as f:
            f.write(io.dumps(data, indent=1).encode())

    def get_state(app):
        if not io.path.exists(app.conf): raise io.Errdetail("Proxy configuration file not found!")

        with open(app.conf, "rb") as f:
            state = io.loads(f.read())

        if io.path.exists(state.get("blazeio_proxy_hosts")):
            with open(state.get("blazeio_proxy_hosts"), "rb") as f:
                try: state["hosts"] = io.loads(f.read())
                except: state["hosts"] = {}

        return state 

    async def add_to_proxy(app, host: str, port: int, certfile: (None, str) = None, keyfile: (None, str) = None, hostname: str = "127.0.0.1", ow: bool = False, in_try: (int, bool) = False, **kw):
        if not in_try:
            try: return await app.add_to_proxy(host, port, certfile, keyfile, hostname, ow, in_try = True, **kw)
            except RuntimeError: return
            except Exception as e: return await io.traceback_logger(e)

        if (idx := host.rfind(":")) != -1:
            host = host[:idx]

        state = app.get_state()
        ssl = io.ssl_context if state.get("Blazeio.Other.proxy.ssl") else None

        host_data = {
            "remote": "http://%s:%d" % (hostname, port),
            "port": port,
            "certfile": certfile,
            "keyfile": keyfile,
            "server_address": "%s://%s:%d" % ("https" if ssl else "http", host,  int(state.get("Blazeio.Other.proxy.port")))
        }

        if not ow and state.get("hosts"):
            if io.dumps(srv := state["hosts"].get(host, {})) == io.dumps(host_data): return host_data

        async with io.Session.post("%s://127.0.0.1:%d/remote_webhook" % ("https" if ssl else "http", int(state.get("Blazeio.Other.proxy.port"))), {"host": state.get("server_name"), "route": "/remote_webhook"}, json = {host: host_data}, ssl = ssl, add_host = False) as session:
            if not ow: await io.plog.cyan("Proxy.add_to_proxy", await session.text())

        return host_data
    
    async def available(app):
        if app.availablity is not None:
            return app.availablity

        try:
            state = app.get_state()
            async with io.Session(state.get("server_address") + "/discover", "get", headers = {"host": state.get("server_name"), "route": "/discover"}, ssl = io.ssl_context if state.get("Blazeio.Other.proxy.ssl") else None, add_host = False) as session:
                app.availablity = await session.data()

        except (OSError, io.Errdetail):
            app.availablity = False

        return app.availablity

scope.whclient = WebhookClient()

add_to_proxy = lambda *a, **k: io.ioConf.run(scope.whclient.add_to_proxy(*a, **k))
available = lambda *a, **k: io.ioConf.run(scope.whclient.available(*a, **k))

def runner(args, web_runner = None):
    scope.web = io.App(args.host, args.port, __timeout__ = float((60**2) * 24))

    io.ioConf.INBOUND_CHUNK_SIZE, io.ioConf.OUTBOUND_CHUNK_SIZE = args.INBOUND_CHUNK_SIZE, args.OUTBOUND_CHUNK_SIZE

    scope.web.attach(app := App(proxy_port = args.port, fresh = args.fresh))

    conf = io.Dot_Dict()

    if args.ssl:
        app.transporter = app.tls_transporter
        conf.ssl = app.configure_ssl()

    state = app.json()

    state.update({
        "Blazeio.Other.proxy.port": args.port,
        "Blazeio.Other.proxy.ssl": True if args.ssl else False,
        "server_name": scope.server_name,
        "server_address": "%s://127.0.0.1:%d" % ("https" if conf.ssl else "http", int(args.port)),
        **{str(key): str(val) for key,val in args.__dict__.items()}
    })

    scope.whclient.save_state(state)

    scope.web.sock().setsockopt(io.SOL_SOCKET, io.SO_REUSEPORT, 1)
    scope.server_set.set()

    if not web_runner: web_runner = scope.web.run
    else: web_runner = scope.web.runner

    return web_runner(**conf._dict)

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-port", "--port", type = int, default = 8080)
    parser.add_argument("-ssl", "--ssl", action = "store_true")
    parser.add_argument("-INBOUND_CHUNK_SIZE", "--INBOUND_CHUNK_SIZE", type = int, default = 1024*100)
    parser.add_argument("-OUTBOUND_CHUNK_SIZE", "--OUTBOUND_CHUNK_SIZE", type = int, default = 1024*100)
    parser.add_argument("-host", "--host", default = "0.0.0.0")
    
    for i in ("fresh",):
        parser.add_argument("-%s" % i, "--%s" % i, action = "store_true")

    args = parser.parse_args()
    runner(args, True)
