# Blazeio.Bench.__main__.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser

from .Modules import Utils, Server, Client, Runner

from os import walk

io.Scope.add_imports(globals())

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*4, 1024*4

io.Scope.web = io.App("0.0.0.0", 8005, name = "io.Scope.web", with_keepalive = True)

@io.Scope.instantiate
class App:
    formats: dict = io.ddict(
        serve_files = io.ddict(
            delimiters = io.ddict(
                rrf = "::"
            )
        )
    )
    cwd: str = io.getcwd()

class Main(Client.Manager, Utils.Manager, Runner.Manager):
    __slots__ = ("c", "d", "payload_size", "url", "m", "payload", "serialize_connections", "conns", "writes", "runner_notified", "is_local", "analytics", "perf_counter", "benchmark", "serve_files", "rawsrv", "payloadsrv")
    serializer = io.ioCondition()
    sync_serializer = io.ioCondition()
    request_metrics = ("prepare", "http_parsing", "ttfb_io", "ttfb", "body_io", "latency")
    metric_types = ("elapsed", "rps")
    def __init__(app, url: (str, io.Utype) = "http://%s:%d" % (io.Scope.web.ServerConfig.host, io.Scope.web.ServerConfig.port), c: (int, io.Utype) = 1, d: (int, io.Utype) = 3, m: (str, io.Utype) = "get", payload_size: (int, io.Utype) = 1024, writes: (int, io.Utype) = 1, conns: (list, io.Unone) = [], serialize_connections: (bool, io.Utype) = True, analytics: (list, io.Unone) = [], perf_counter: (int, io.Unone) = io.perf_counter(), benchmark: (bool, int, class_parser.Store, io.Utype) = False, serve_files: (str, io.Utype) = "", rawsrv: (bool, int, class_parser.Store, io.Utype) = False, payloadsrv: (bool, int, class_parser.Store, io.Utype) = False):
        io.set_from_args(app, locals(), (io.Utype, io.Unone))
        app.is_local = app.url.startswith("http://%s:%d/" % (io.Scope.web.ServerConfig.host, io.Scope.web.ServerConfig.port))
        io.Super(app).__init__()
        app.add_servers()

    def add_servers(app):
        if app.rawsrv:
            io.Scope.web.attach(Server.RawServer(app.payload_size, app.writes))

        else:
            io.Scope.web.attach(Server.PayloadServer(app.payload_size, app.writes))

        if app.serve_files:
            if app.serve_files.find(io.Scope.App.formats.serve_files.delimiters.rrf) == -1:
                raise io.Err("serve_files requires the (%s)(root/root_dir/files) delimiter" % io.Scope.App.formats.serve_files.delimiters.rrf)

            io.Scope.web.attach(Server.FileServer(*app.serve_files.split(io.Scope.App.formats.serve_files.delimiters.rrf)))

if __name__ == "__main__":
    io.TCPOptimizer(io.Scope.web)

    with io.Scope.web:
        Main(**class_parser.Parser(Main, io.Utype).args())
        io.Scope.web.runner()
