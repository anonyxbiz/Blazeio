import Blazeio as io
import Blazeio.Other.class_parser as class_parser
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

scope = io.ddict(server_set = io.SharpEvent(), privileged_domain = "blazeio.", server_name = "blazeio.other.proxy.localhost", parent_dir = "Blazeio_Other_Proxy", access_key = None)

class Pathops:
    __slots__ = ("parent", "cert_dir", "dirs")
    def __init__(app): ...

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

class Taskmanager:
    def __init__(app): ...

    def create_task(app, coro):
        app.tasks.append(task := io.create_task(coro))
        task.add_done_callback(lambda task: app.tasks.remove(task))
        return task

class Dbstuff:
    def __init__(app):
        app.updaters_coordination = io.ddict(sync = io.ioCondition(), previous_size = 0, interval = 30)

    async def update_file_db(app):
        async with app.updaters_coordination.sync:
            async with app.host_update_cond:
                data = io.anydumps({key: {a:b for a, b in val.items() if a not in ("conn",)} for key, val in app.hosts.items()}).encode()
                await io.asave(app.blazeio_proxy_hosts, data)
                app.updaters_coordination.previous_size = len(data)

    async def update_hosts_daemon(app):
        await app.web
        while True:
            if io.path.exists(app.blazeio_proxy_hosts):
                if (size := io.path.getsize(app.blazeio_proxy_hosts)) != app.updaters_coordination.previous_size:
                    app.updaters_coordination.previous_size = size
                    async with app.updaters_coordination.sync:
                        app.hosts.update(io.Dotify(io.loads(await io.aread(app.blazeio_proxy_hosts))))
                        await io.plog.cyan("loaded hosts from: %s" % app.blazeio_proxy_hosts, io.anydumps(app.hosts, indent=1))

            await io.sleep(app.updaters_coordination.interval)

class Sslproxy:
    def __init__(app):
        app.ssl_configs = io.ddict(certfile = "proxytest.cert", keyfile = "proxytest.pem")
        app.cert_dir = Path_manager.cert_dir
        app.ssl_contexts = io.ddict()

    def sni_callback(app, ssl_socket, server_name, ssl_context):
        if not server_name:
            server_name = scope.server_name

        if server_name and (server := app.hosts.get(server_name, app.wildcard_srv(server_name))) is not None:
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

class MuxTransporter:
    def __init__(app):
        app.__conn__ = io.ioCondition()
        app.__serialize__ = io.ioCondition()

    def is_conn(app, srv):
        if not (conn := srv.get("conn")) or (not conn.protocol) or (conn.protocol.transport.is_closing()): return
        return conn

    async def conn(app, srv):
        if not (conn := app.is_conn(srv)):
            async with app.__conn__:
                if not (conn := app.is_conn(srv)):
                    srv.conn = (conn := await io.Session(srv.remote, client_protocol = Protocols.client, connect_only = 1))
    
        return await srv.conn.create_stream()

    async def mux_puller(app, r, resp):
        try:
            while (chunk := await r): await resp.writer(chunk)
            await resp.__eof__()
        except:
            return

    async def mux_transporter(app, r, srv: io.ddict):
        task = None
        async with io.Session(srv.remote, use_protocol = await app.conn(srv), add_host = False, connect_only = True, decode_resp = False) as resp:
            await resp.writer(io.ioConf.gen_payload(r.method, r.headers, r.tail, str(resp.port)))

            if r.method not in r.non_bodied_methods:
                task = io.create_task(app.mux_puller(r, resp))
            else:
                async with resp.protocol: ...

            async for chunk in resp.__pull__():
                if chunk:
                    await r.writer(chunk)

        if task:
            async with io.Ehandler(exit_on_err = 1, ignore = io.CancelledError): await task

class Transporter:
    def __init__(app): ...

    async def puller(app, r, resp):
        try:
            async for chunk in r: await resp.push(chunk)
        except (io.CancelledError, RuntimeError):
            ...

    async def transporter(app, r, srv: io.ddict):
        async with io.BlazeioClient(srv.hostname, srv.port, ssl = None, __chunk_size__ = int(srv.get("OUTBOUND_CHUNK_SIZE", io.ioConf.OUTBOUND_CHUNK_SIZE))) as resp:
            await resp.push(io.ioConf.gen_payload(r.method, r.headers, r.tail, str(srv.port)))

            task = io.create_task(app.puller(r, resp))

            async for chunk in resp:
                if chunk:
                    await r.writer(chunk)

            if not task.done(): task.cancel()

            await task

class Sutils:
    def __init__(app): ...

    def json(app):
        data = io.ddict()
        for key in app.__slots__:
            if not isinstance(val := getattr(app, key), (str, int, dict)):
                val = str(val)

            data[str(key)] = val

        return data

    def is_from_home(app, r, host: str):
        if host.startswith(scope.privileged_domain) and (r.ip_host in app.privileged_ips or r.params().get("access_key") == scope.access_key):
            return True
        else:
            return False

    def wildcard_srv(app, server_hostname: str):
        while (idx := server_hostname.find(".")) != -1:
            server_hostname = server_hostname[idx + 1:]
            if (srv := app.hosts.get("*.%s" % server_hostname)): return srv

    @classmethod
    def run_subprocess_sync(app, cmd):
        with ThreadPoolExecutor() as pool:
            return io.getLoop.run_in_executor(pool, lambda: subprocess_run(cmd, shell=True, check=True, capture_output=True))

    @classmethod
    async def from_certbot(app, host: str, port: int):
        async with io.Ehandler(_raise = 0):
            certfile, keyfile = "/etc/letsencrypt/live/%s/fullchain.pem" % host, "/etc/letsencrypt/live/%s/privkey.pem" % host

            if not io.path.exists(certfile) or not io.path.exists(keyfile):
                cmd = "certbot certonly --standalone --domain %s --http-01-port %d" % (host, port)

                await io.plog.yellow("Running command", cmd)

                proc = await app.run_subprocess_sync(cmd)

                await io.plog.yellow(proc.stdout.decode(), proc.stderr.decode())

                if not io.path.exists(certfile) or not io.path.exists(keyfile): raise io.Err("certficate not found")

            certfile_cp = io.path.join(Path_manager.cert_dir, host + io.path.basename(certfile))
            keyfile_cp = io.path.join(Path_manager.cert_dir, host + io.path.basename(keyfile))
    
            if not io.path.exists(certfile_cp) or not io.path.exists(keyfile_cp):
                for parent, new in ((certfile, certfile_cp), (keyfile, keyfile_cp)):
                    await io.asave(new, await io.aread(parent))

            return (certfile_cp, keyfile_cp)

class Routes:
    def __init__(app): ...

    async def _remote_webhook(app, r):
        json = io.Dotify(await r.get_json())
        hostname = list(json.keys())[0]
        host = json[hostname]

        if host.get("from_certbot", False):
            app.hosts[hostname] = io.ddict(**host, pending_certbot = True)

            await io.plog.yellow(io.anydumps(app.hosts))

            await io.sleep(60*10)
            host["certfile"], host["keyfile"] = await app.from_certbot(hostname, int(host.get("port")))

        app.hosts.update(json)

        await app.update_file_db()

        await io.plog.cyan("remote_webhook", "added: %s" % io.anydumps(json, indent=1))

        await io.Deliver.json(json)

    async def _discover(app, r):
        await io.Deliver.text('{"discovered": true}', headers = {"Content-type": "application/json; charset=utf-8"})

    async def _proxy_state(app, r):
        await io.Deliver.json({key: str(val) if not isinstance(val := getattr(app, key, None), (int, dict, str)) else (val if not isinstance(val, dict) else {k: str(v) if not isinstance(v, (int, str)) else v for k, v in val.items()}) for key in app.__slots__}, indent = 4)

class Protocolmanagers:
    def __init__(app): ...

    async def logger(app, r, i):
        await io.plog.cyan("%s:%d | %s@%s%s" % (r.ip_host, r.ip_port, r.method.upper(), i[-1], r.tail), ", ".join(["(%s=%s)" % (i, str(getattr(r, i, ""))[:100]) for i in r.__slots__]))

    def update_protocol_event(app):
        if not app.protocol_update_event.is_set(): app.protocol_update_event.set()

    async def protocol_manager(app):
        while 1:
            await app.protocol_update_event.wait_clear()

            for i in list(app.protocols):
                if not (r := app.protocols.get(i)): continue

                if app.log: await app.logger(r, i)
    
                if (elapsed := float(io.perf_counter() - r.__perf_counter__)) >= app.timeout:
                    r.cancel(str(io.Protocoltimeout()))
                    app.protocols.pop(r.identifier)

class Server(Routes):
    def __init__(app): ...

    async def __main_handler__(app, r):
        app.protocol_count += 1
        r.identifier = app.protocol_count
        r.__perf_counter__ = io.perf_counter()

        sock = r.transport.get_extra_info("ssl_object")

        await scope.web.parse_default(r)

        r.headers["ip_host"] = str(r.ip_host)
        r.headers["ip_port"] = str(r.ip_port)

        if sock:
            server_hostname = sock.context.server_hostname
        else:
            if (idx := (server_hostname := r.headers.get("Host", "")).rfind(":")) != -1:
                server_hostname = server_hostname[:idx]

        if app.is_from_home(r, server_hostname):
            if not (route := getattr(app, r.headers.get("route", r.path.replace("/", "_")), None)):
                raise io.Abort("Not Found", 404)

            raise io.Eof(await route(r))

        if not (srv := app.hosts.get(server_hostname, app.wildcard_srv(server_hostname))) or not (remote := srv.get("remote")):
            raise io.Abort("Server could not be found", 503)

        if not sock and not srv.get("pending_certbot", None) and srv.server_config.enforce_https:
            raise io.Abort("Permanent Redirect", 308, io.ddict(location = "https://%s:%s%s" % (server_hostname, io.Scope.args.get("port", 443), r.tail)))

        try:
            app.protocols[r.identifier] = r
            app.update_protocol_event()
            if srv.server_config.multiplexed:
                await app.mux_transporter(r, srv)
            else:
                await app.transporter(r, srv)
        except OSError:
            raise io.Abort("Service Unavailable", 500)
        except io.ClientDisconnected:
            ...
        finally:
            app.protocols.pop(r.identifier, None)
            app.update_protocol_event()

class Proxy(Taskmanager, Dbstuff, Sslproxy, Transporter, MuxTransporter, Sutils, Protocolmanagers, Server):
    __slots__ = ("hosts", "tasks", "protocols", "protocol_count", "host_update_cond", "protocol_update_event", "timeout", "blazeio_proxy_hosts", "log", "track_metrics", "ssl", "ssl_configs", "cert_dir", "ssl_contexts", "__conn__", "__serialize__", "keepalive", "enforce_https", "proxy_port", "web", "privileged_ips", "updaters_coordination")
    def __init__(app, blazeio_proxy_hosts: (str, io.Utype) = "blazeio_proxy_hosts.txt", timeout: (int, io.Utype) = float(60*10), log: (bool, io.Utype) = False, track_metrics: (bool, io.Utype) = True, proxy_port: (bool, int, io.Utype) = None, protocols: (dict, io.Utype) = io.ddict(), protocol_count: (int, io.Utype) = 0, tasks: (list, io.Utype) = [], protocol_update_event: (io.SharpEvent, io.Utype) = io.SharpEvent(), host_update_cond: (io.ioCondition, io.Utype) = io.ioCondition(), hosts: (dict, io.Utype) = io.Dotify({scope.server_name: {}, }), ssl: (bool, io.Utype) = False, keepalive: (bool, io.Utype) = True, enforce_https: (bool, io.Utype) = False, web: (io.App, io.Utype) = None, privileged_ips: (str, io.Utype) = "0.0.0.0"):
        io.set_from_args(app, locals(), io.Utype)
        io.Super(app).__init__()
        app.privileged_ips = tuple(["127.0.0.1", *app.privileged_ips.split(",")])
        app.blazeio_proxy_hosts = io.path.join(scope.HOME, blazeio_proxy_hosts)

        web.add_callback(web.on_run_callbacks, io.plog.magenta("Blazeio Proxy (Version: %s)" % io.__version__, "PID: %s" % io.pid, "Server [%s] running on %s" % (web.server_name, web.ServerConfig.server_address), io.anydumps({key: getattr(app, key, None) or getattr(scope, key, None) for key in ("privileged_ips", "privileged_domain", "server_name", "access_key")}, indent = 1), func = app.__init__))

        for coro in (app.update_hosts_daemon(), app.protocol_manager()): app.create_task(coro)

class App(Proxy): ...

class WebhookClient:
    __slots__ = ("conf", "availablity")
    def __init__(app):
        app.conf = io.path.join(scope.HOME, "conf")
        app.availablity = None

    def save_state(app, data: dict):
        with open(app.conf, "wb") as f:
            f.write(io.anydumps(data, indent=1).encode())

    def get_state(app):
        if not io.path.exists(app.conf): raise io.Errdetail("Proxy configuration file not found!")

        with open(app.conf, "rb") as f:
            state = io.loads(f.read())

        if io.path.exists(state.get("blazeio_proxy_hosts")):
            with open(state.get("blazeio_proxy_hosts"), "rb") as f:
                try: state["hosts"] = io.loads(f.read())
                except: state["hosts"] = {}

        return state 

    async def add_to_proxy(app, host: str, port: int, certfile: (None, str) = None, keyfile: (None, str) = None, hostname: str = "127.0.0.1", ow: bool = False, from_certbot: bool = False, multiplexed: bool = False, enforce_https: bool = True, in_try: (int, bool) = False, **kw):
        if not in_try:
            try: return await app.add_to_proxy(host, port, certfile, keyfile, hostname, ow, from_certbot, multiplexed, enforce_https, in_try = True, **kw)
            except RuntimeError: return
            except io.ServerDisconnected: return
            except Exception as e: return await io.traceback_logger(e)

        if (idx := host.rfind(":")) != -1:
            host = host[:idx]

        state = app.get_state()
        ssl = io.ssl_context if state.get("Blazeio.Other.proxy.ssl") else None

        host_data = {
            "hostname": hostname,
            "port": port,
            "from_certbot": from_certbot,
            "remote": "http://%s:%d" % (hostname, port),
            "certfile": certfile,
            "keyfile": keyfile,
            "server_address": "%s://%s:%d" % ("https" if ssl else "http", host,  int(state.get("Blazeio.Other.proxy.port"))),
            "server_config": {
                "multiplexed": multiplexed,
                "enforce_https": enforce_https
            }
        }

        if not ow and state.get("hosts"):
            if io.anydumps(srv := state["hosts"].get(host, {})) == io.anydumps(host_data): return host_data

        async with io.getSession.post("%s://127.0.0.1:%d/remote_webhook" % ("https" if ssl else "http", int(state.get("Blazeio.Other.proxy.port"))), {"host": state.get("server_name"), "route": "/remote_webhook"}, json = {host: host_data}, ssl = ssl, add_host = False) as session:
            if not ow: await io.plog.cyan("Proxy.add_to_proxy", await session.text())

        return host_data
    
    async def available(app):
        if app.availablity is not None:
            return app.availablity

        try:
            state = app.get_state()

            ssl = io.ssl_context if state.get("Blazeio.Other.proxy.ssl") else None
            async with io.getSession("%s://127.0.0.1:%d/discover" % ("https" if ssl else "http", int(state.get("Blazeio.Other.proxy.port"))), "get", headers = {"host": state.get("server_name"), "route": "/discover"}, ssl = ssl, add_host = False) as session:
                app.availablity = await session.data()

        except (OSError, io.Errdetail):
            app.availablity = False

        return app.availablity

scope.whclient = WebhookClient()

add_to_proxy = lambda *a, **k: io.ioConf.run(scope.whclient.add_to_proxy(*a, **k))
available = lambda *a, **k: io.ioConf.run(scope.whclient.available(*a, **k))

class Runner:
    def __init__(app, port: (int, io.Utype) = 8080, http_port: (int, io.Utype) = 0, INBOUND_CHUNK_SIZE: (int, io.Utype) = 1024*100, OUTBOUND_CHUNK_SIZE: (int, io.Utype) = 1024*100, host: (str, io.Utype) = "0.0.0.0", ssl: (bool, class_parser.Store_true, io.Utype) = False, fresh: (bool, class_parser.Store_true, io.Utype) = False, web_runner: (bool, class_parser.Store_true, io.Utype) = False, keepalive: (bool, class_parser.Store_true, io.Utype) = False, enforce_https: (bool, class_parser.Store_true, io.Utype) = False, privileged_ips: (str, io.Utype) = "0.0.0.0", access_key: (str, io.Utype) = io.environ.get("blazeio.proxy.access_key", None) or io.token_urlsafe(16)):
        app.args = io.ddict()
        io.set_from_args(app, locals(), io.Utype, app.args)
        scope.access_key = app.args.access_key

    def __enter__(app):
        return app
    
    def __exit__(app, *args):
        return False
    
    def gen_web(app, srv):
        web = srv.server
        if (INBOUND_CHUNK_SIZE := app.args.get("INBOUND_CHUNK_SIZE")): io.ioConf.INBOUND_CHUNK_SIZE = INBOUND_CHUNK_SIZE
        if (OUTBOUND_CHUNK_SIZE := app.args.get("INBOUND_CHUNK_SIZE")): io.ioConf.OUTBOUND_CHUNK_SIZE = OUTBOUND_CHUNK_SIZE

        web.attach(main_app := Proxy(proxy_port = srv.port, ssl = srv.ssl, web = web, **{key: val for key, val in app.args.items() if key in Proxy.__slots__ and key not in srv}))

        if srv.ssl:
            srv.conf.ssl = main_app.configure_ssl()
        else:
            srv.conf.ssl = None

        state = main_app.json()
        scope.state = state

        state.update({
            "Blazeio.Other.proxy.port": srv.port,
            "Blazeio.Other.proxy.ssl": True if srv.ssl else False,
            "server_name": scope.server_name,
            "ssl": srv.ssl,
            "server_port": srv.port,
            "server_address": "%s://127.0.0.1:%d" % ("https" if srv.conf.ssl else "http", int(srv.port)),
            **{str(key): str(val) for key, val in app.args.items()}
        })

        scope.whclient.save_state(state)

        if SO_REUSEPORT: web.sock().setsockopt(SOL_SOCKET, SO_REUSEPORT, 1)

        scope.server_set.set()

        if app.args.keepalive: web.with_keepalive()

        return web

    def __call__(app, **kwargs):
        if app.args.fresh:
            rmtree(scope.HOME)
            Path_manager()

        srvs = []
    
        srvs.append(io.ddict(server = io.App(app.args.host, (port := int(app.args.port)), __timeout__ = float((60**2) * 24), name = "Blazeio_Other_Proxy"), conf = io.ddict(), ssl = app.args.ssl, port = port, task = None))

        if app.args.ssl:
            srvs.append(io.ddict(server = io.App(app.args.host, (port := (int(app.args.http_port) or int(app.args.port)-1)), __timeout__ = float((60**2) * 24), name = "Blazeio_Other_Proxy"), conf = io.ddict(), ssl = False, port = port, task = None))

        for i, srv in enumerate(srvs):
            scope.web = app.gen_web(srv)
            if i != (len(srvs) - 1):
                srv.task = io.create_task(scope.web.run(**srv.conf))

        if app.args.web_runner:
            return scope.web.run(**srv.conf)

        with scope.web:
            scope.web.runner(**srv.conf)

if __name__ == "__main__":
    parser = class_parser.Parser(Runner, io.Utype)
    io.Scope.args = parser.args()
    with Runner(**io.Scope.args) as runner:
        runner()