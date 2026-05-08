# Blazeio.Bench.__main__.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser

from .Modules import Utils, Server, Client, Runner

io.ioConf.OUTBOUND_CHUNK_SIZE, io.ioConf.INBOUND_CHUNK_SIZE = 1024*4, 1024*4

io.Scope.web = io.App("0.0.0.0", 6000, name = "io.Scope.web", with_keepalive = True)

class Main(Server.Manager, Client.Manager, Utils.Manager, Runner.Manager):
    __slots__ = ("c", "d", "payload_size", "url", "m", "payload", "serialize_connections", "conns", "writes", "runner_notified", "is_local", "analytics", "perf_counter", "server_only")
    serializer = io.ioCondition()
    sync_serializer = io.ioCondition()
    request_metrics = ("prepare", "http_parsing", "ttfb_io", "ttfb", "body_io", "latency")
    metric_types = ("elapsed", "rps")

    def __init__(app, url: (str, io.Utype) = "http://%s:%d" % (io.Scope.web.ServerConfig.host, io.Scope.web.ServerConfig.port), c: (int, io.Utype) = 1, d: (int, io.Utype) = 3, m: (str, io.Utype) = "get", payload_size: (int, io.Utype) = 1024, writes: (int, io.Utype) = 1, conns: (list, io.Unone) = [], serialize_connections: (bool, io.Utype) = True, analytics: (list, io.Unone) = [], perf_counter: (int, io.Unone) = io.perf_counter(), server_only: (bool, int, class_parser.Store, io.Utype) = False):
        io.set_from_args(app, locals(), (io.Utype, io.Unone))
        app.is_local = app.url.startswith("http://%s:%d" % (io.Scope.web.ServerConfig.host, io.Scope.web.ServerConfig.port))
        io.Super(app).__init__()

if __name__ == "__main__":
    with io.Scope.web:
        io.Scope.web.attach(Main(**class_parser.Parser(Main, io.Utype).args()))
        io.Scope.web.runner()
