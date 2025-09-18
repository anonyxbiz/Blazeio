import Blazeio as io
from os import mkdir, access as os_access, R_OK as os_R_OK, W_OK as os_W_OK, X_OK as os_X_OK, makedirs
from pathlib import Path
from ssl import TLSVersion
from Blazeio.Protocols.multiplexer import Protocols
from concurrent.futures import ThreadPoolExecutor
from subprocess import PIPE, run as subprocess_run
from shutil import rmtree
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, IPPROTO_TCP, TCP_NODELAY, SHUT_RDWR, SO_KEEPALIVE, TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT

try:
    from socket import SO_REUSEPORT
except ImportError:
    SO_REUSEPORT = None

scope = io.ddict(server_name = "blazeio.other.multiplexed_proxy.localhost", parent_dir = "Blazeio_Other_Multiplexed_proxy", server_set = io.SharpEvent(False, io.loop))

class Pathops:
    __slots__ = ("parent", "cert_dir", "dirs")
    def __init__(app):
        ...

    def __call__(app):
        app.dirs = []
        app.parent = app.add_dir(io.path.abspath(io.path.join(io.environ.get('HOME', io.environ.get("USERPROFILE")), scope.parent_dir)))
        app.cert_dir = app.add_dir(io.path.join(app.parent, "cert_dir"))
        scope.HOME = app.parent
        app.ensure_dirs()

    def add_dir(app, _dir: str):
        app.dirs.append(_dir)
        return _dir

    def ensure_dirs(app):
        for _dir in app.dirs:
            makedirs(_dir, exist_ok=True)

Path_manager = Pathops()
Path_manager()

class Sslproxy:
    __slots__ = ()
    def __init__(app):
        app.ssl_configs = io.ddict(certfile = "proxytest.cert", keyfile = "proxytest.pem")
        app.cert_dir = Path_manager.cert_dir
        app.ssl_contexts = io.ddict()

    def sni_callback(app, ssl_socket, server_name, ssl_context):
        if not server_name:
            server_name = scope.server_name

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
    def __init__(app):
        app.__conn__ = io.ioCondition(evloop = io.loop)
        app.__serialize__ = io.ioCondition(evloop = io.loop)

    def is_conn(app, srv):
        if not (conn := srv.get("conn")) or (not conn.protocol) or (conn.protocol.transport.is_closing()): return
        return conn

    async def puller(app, r, resp):
        try:
            while (chunk := await r): await resp.writer(chunk)
            await resp.__eof__()
        except:
            return

    async def create_conn(app, srv):
        try:
            return await io.Session(srv.remote, client_protocol = Protocols.client, connect_only = 1)
        except (OSError, Exception):
            srv.pop("conn", False)
            raise io.Abort("Service Unavailable", 500)

    async def conn(app, srv):
        if not (conn := app.is_conn(srv)):
            async with app.__conn__:
                if not (conn := app.is_conn(srv)):
                    srv.conn = await app.create_conn(srv)

        return await srv.conn.create_stream()

    async def transporter(app, r, srv: io.ddict):
        task = None
        async with io.Session(srv.remote, use_protocol = await app.conn(srv), add_host = False, connect_only = True, decode_resp = False) as resp:
            await resp.writer(io.ioConf.gen_payload(r.method, r.headers, r.tail, str(resp.port)))

            if r.method not in r.non_bodied_methods:
                task = io.create_task(app.puller(r, resp))
            else:
                async with resp.protocol: ...

            # await resp.prepare_http()

            # await r.prepare(resp.headers, resp.status_code, resp.reason_phrase, encode_resp = False, encode_event_stream = False)

            async for chunk in resp.__pull__():
                if chunk:
                    r.lazy_writer.chunk_pool.append(chunk)
                    if len(r.lazy_writer.chunk_pool) >= r.lazy_writer.min_chunks:
                        while len(r.lazy_writer.chunk_pool) > r.lazy_writer.lazy_chunks: await r.writer(r.lazy_writer.chunk_pool.popleft())
        if task:
            if not task.done(): task.cancel()

class App(Sslproxy, Transporters):
    __slots__ = ("hosts", "tasks", "protocols", "protocol_count", "host_update_cond", "protocol_update_event", "timeout", "blazeio_proxy_hosts", "log", "track_metrics", "ssl", "ssl_configs", "cert_dir", "ssl_contexts", "__conn__", "__serialize__", "keepalive", "enforce_https")
    def __init__(app, blazeio_proxy_hosts = "blazeio_proxy_hosts.txt", timeout = float(60*10), log = False, track_metrics = True, proxy_port = None, protocols = {}, protocol_count = 0, tasks = [], protocol_update_event = io.SharpEvent(True, io.ioConf.loop), host_update_cond = io.ioCondition(evloop = io.ioConf.loop), hosts = io.Dotify({scope.server_name: {}}), ssl: bool = False, keepalive: bool = True, enforce_https: bool = False):
        io.Super(app).__init__()
        for key in (__locals__ := locals()):
            if key not in app.__slots__: continue
            if getattr(app, key, NotImplemented) != NotImplemented: continue
            setattr(app, key, __locals__[key])

        app.blazeio_proxy_hosts = io.path.join(scope.HOME, blazeio_proxy_hosts)

        if app.log:
            io.loop.create_task(io.log.debug("blazeio_proxy_hosts: %s" % app.blazeio_proxy_hosts))

        app.tasks.append(io.ioConf.loop.create_task(app.update_mem_db()))
        app.tasks.append(io.ioConf.loop.create_task(app.protocol_manager()))

    def json(app):
        data = io.ddict()
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
        if not io.path.exists(app.blazeio_proxy_hosts): return

        async with io.async_open(app.blazeio_proxy_hosts, "rb") as f:
            app.hosts.update(io.Dotify(io.loads(await f.read())))

        await io.plog.cyan("update_mem_db", "loaded: %s" % io.dumps(app.hosts, indent=4, escape_forward_slashes = False))

    async def _remote_webhook(app, r):
        app.hosts.update(io.Dotify(json := await io.Request.get_json(r)))

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

    async def __default_handler__(app, r):
        app.protocol_count += 1
        r.identifier = app.protocol_count
        r.__perf_counter__ = io.perf_counter()
        r.store = io.ddict(lazy_writer = io.ddict(chunk_pool = io.deque(), min_chunks = 3, lazy_chunks = 2))

        sock = r.transport.get_extra_info("ssl_object")

        await scope.web.parse_default(r)
        
        if sock:
            server_hostname = sock.context.server_hostname
        else:
            if (idx := (server_hostname := r.headers.get("Host", "")).rfind(":")) != -1:
                server_hostname = server_hostname[:idx]

        if app.is_from_home(r, server_hostname):
            if not (route := getattr(app, r.headers.get("route", r.path.replace("/", "_")), None)):
                raise io.Abort("Not Found", 404)
            return await route(r)

        if not (srv := app.hosts.get(server_hostname)) or not (remote := srv.get("remote")):
            raise io.Abort("Server could not be found", 503)

        if not sock and app.enforce_https:
            raise io.Abort("https upgrade", 302, io.ddict(location = "https://%s:%s%s" % (server_hostname, io.Scope.args.port, r.tail)))

        try:
            if not r.pull: r.pull = r.request
            app.protocols[r.identifier] = r
            if not app.protocol_update_event.is_set(): app.protocol_update_event.set()

            await app.transporter(r, srv)
            while r.lazy_writer.chunk_pool:
                await r.writer(r.lazy_writer.chunk_pool.popleft())
        finally:
            app.protocols.pop(r.identifier, None)
            if not app.protocol_update_event.is_set(): app.protocol_update_event.set()

    async def __main_handler__(app, r):
        if not app.keepalive: return await app.__default_handler__(r)

        while not r.transport.is_closing():
            try:
                exc = None
                await app.__default_handler__(r)
            except (io.Abort, io.Eof, io.Err, io.ServerGotInTrouble) as e:
                if isinstance(e, io.Abort): await e.text(r)
            except Exception as e:
                exc = e
            finally:
                if exc: raise exc
                r.utils.clear_protocol(r)

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
  
    def run_subprocess_sync(app, cmd):
        with ThreadPoolExecutor() as pool:
            return io.get_event_loop().run_in_executor(pool, lambda: subprocess_run(cmd, shell=True, check=True, capture_output=True))

    async def from_certbot(app, host):
        certfile = "/etc/letsencrypt/live/%s/fullchain.pem" % host
        keyfile = "/etc/letsencrypt/live/%s/privkey.pem" % host

        if not io.path.exists(certfile) or not io.path.exists(keyfile):
            proc = await app.run_subprocess_sync("sudo certbot certonly --standalone --domain %s" % host)

            await io.plog.yellow(proc.stdout.decode(), proc.stderr.decode())

            if not io.path.exists(certfile) or not io.path.exists(keyfile): raise io.Err("certficate not found")

        certfile_cp = io.path.join(Path_manager.cert_dir, host + io.path.basename(certfile))
        keyfile_cp = io.path.join(Path_manager.cert_dir, host + io.path.basename(keyfile))

        if not io.path.exists(certfile_cp) or not io.path.exists(keyfile_cp):
            for parent, new in ((certfile, certfile_cp), (keyfile, keyfile_cp)):
                async with io.async_open(parent, "rb") as f:
                    content = await f.read()
                async with io.async_open(new, "wb") as f:
                    await f.write(content)

        return (certfile_cp, keyfile_cp)

    async def add_to_proxy(app, host: str, port: int, certfile: (None, str) = None, keyfile: (None, str) = None, hostname: str = "127.0.0.1", ow: bool = False, from_certbot: bool = False, in_try: (int, bool) = False, **kw):
        if not in_try:
            try: return await app.add_to_proxy(host, port, certfile, keyfile, hostname, ow, from_certbot, in_try = True, **kw)
            except RuntimeError: return
            except io.ServerDisconnected: return
            except Exception as e: return await io.traceback_logger(e)

        if (idx := host.rfind(":")) != -1:
            host = host[:idx]

        state = app.get_state()
        ssl = io.ssl_context if state.get("Blazeio.Other.multiplexed_proxy.ssl") else None
        
        if from_certbot:
            certfile, keyfile = await app.from_certbot(host)

        host_data = {
            "hostname": hostname,
            "port": port,
            "remote": "http://%s:%d" % (hostname, port),
            "certfile": certfile,
            "keyfile": keyfile,
            "server_address": "%s://%s:%d" % ("https" if ssl else "http", host,  int(state.get("Blazeio.Other.multiplexed_proxy.port")))
        }

        if not ow and state.get("hosts"):
            if io.dumps(srv := state["hosts"].get(host, {})) == io.dumps(host_data): return host_data

        async with io.Session.post("%s://127.0.0.1:%d/remote_webhook" % ("https" if ssl else "http", int(state.get("Blazeio.Other.multiplexed_proxy.port"))), {"host": state.get("server_name"), "route": "/remote_webhook"}, json = {host: host_data}, ssl = ssl, add_host = False) as session:
            if not ow: await io.plog.cyan("Proxy.add_to_proxy", await session.text())

        return host_data
    
    async def available(app):
        if app.availablity is not None:
            return app.availablity

        try:
            state = app.get_state()
            
            ssl = io.ssl_context if state.get("Blazeio.Other.multiplexed_proxy.ssl") else None
            async with io.Session("%s://127.0.0.1:%d/discover" % ("https" if ssl else "http", int(state.get("Blazeio.Other.multiplexed_proxy.port"))), "get", headers = {"host": state.get("server_name"), "route": "/discover"}, ssl = ssl, add_host = False) as session:
                app.availablity = await session.data()

        except (OSError, io.Errdetail):
            app.availablity = False

        return app.availablity

scope.whclient = WebhookClient()

add_to_proxy = lambda *a, **k: io.ioConf.run(scope.whclient.add_to_proxy(*a, **k))
available = lambda *a, **k: io.ioConf.run(scope.whclient.available(*a, **k))

class Runner:
    def __init__(app, args: io.Utype):
        io.load_from_locals(app, app.__init__, locals(), io.Utype)

    def __enter__(app):
        return app
    
    def __exit__(app, *args):
        return False
    
    def gen_web(app, srv):
        web = srv.server
        if (INBOUND_CHUNK_SIZE := app.args.get("INBOUND_CHUNK_SIZE")): io.ioConf.INBOUND_CHUNK_SIZE = INBOUND_CHUNK_SIZE
        if (OUTBOUND_CHUNK_SIZE := app.args.get("INBOUND_CHUNK_SIZE")): io.ioConf.OUTBOUND_CHUNK_SIZE = OUTBOUND_CHUNK_SIZE

        web.attach(main_app := App(proxy_port = srv.port, ssl = srv.ssl, log = app.args.get("log"), keepalive = app.args.get("keepalive")))

        if srv.ssl:
            srv.conf.ssl = main_app.configure_ssl()
        else:
            srv.conf.ssl = None

        state = main_app.json()
        scope.state = state

        state.update({
            "Blazeio.Other.multiplexed_proxy.port": srv.port,
            "Blazeio.Other.multiplexed_proxy.ssl": True if srv.ssl else False,
            "server_name": scope.server_name,
            "ssl": srv.ssl,
            "server_port": srv.port,
            "server_address": "%s://127.0.0.1:%d" % ("https" if srv.conf.ssl else "http", int(srv.port)),
            **{str(key): str(val) for key, val in app.args.items()}
        })

        scope.whclient.save_state(state)

        if SO_REUSEPORT: web.sock().setsockopt(io.SOL_SOCKET, SO_REUSEPORT, 1)

        scope.server_set.set()

        if app.args.keepalive: web.with_keepalive()

        return web

    def __call__(app, **kwargs):
        if app.args.fresh:
            rmtree(scope.HOME)
            Path_manager()
        
        srvs = []
        
        srvs.append(io.ddict(server = io.App(app.args.host, (port := int(app.args.port)), __timeout__ = float((60**2) * 24), name = "Blazeio_Other_Multiplexed_proxy"), conf = io.ddict(), ssl = app.args.ssl, port = port, task = None))

        if app.args.ssl:
            srvs.append(io.ddict(server = io.App(app.args.host, (port := (int(app.args.http_port) or int(app.args.port)-1)), __timeout__ = float((60**2) * 24), name = "Blazeio_Other_Multiplexed_proxy"), conf = io.ddict(), ssl = False, port = port, task = None))

        for i, srv in enumerate(srvs):
            scope.web = app.gen_web(srv)
            if i != (len(srvs) - 1):
                srv.task = io.create_task(scope.web.run(**srv.conf))

        if app.args.web_runner:
            return scope.web.run(**srv.conf)

        with scope.web:
            scope.web.runner(**srv.conf)

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-port", "--port", type = int, default = 8080)
    parser.add_argument("-http_port", "--http_port", type = int, default = 0)
    parser.add_argument("-INBOUND_CHUNK_SIZE", "--INBOUND_CHUNK_SIZE", type = int, default = 1024*4)
    parser.add_argument("-OUTBOUND_CHUNK_SIZE", "--OUTBOUND_CHUNK_SIZE", type = int, default = 1024*4)
    parser.add_argument("-host", "--host", default = "0.0.0.0")

    for i in ("ssl", "fresh", "web_runner", "keepalive", "enforce_https"):
        parser.add_argument("-%s" % i, "--%s" % i, action = "store_true")

    io.Scope.args = parser.parse_args()
    with Runner(io.ddict(io.Scope.args.__dict__)) as runner:
        runner()