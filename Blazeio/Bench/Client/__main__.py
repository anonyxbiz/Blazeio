# Blazeio.Bench.Client.__main__.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser
from .Modules import app

io.Scope.add_imports(globals())

io.ioConf.OUTBOUND_CHUNK_SIZE = 1024*4

class Main(app.Client):
    __slots__ = ("d", "c", "url", "m", "runner_notified", "perf_counter", )
    serializer = io.ioCondition()
    sync_serializer = io.ioCondition()
    conns, analytics = [], []
    request_metrics, metric_types = ("latency",), ("elapsed", "rps")
    def __init__(app, d: (int, io.Utype, class_parser.Positional) = None, c: (int, io.Utype, class_parser.Positional) = None, url: (str, io.Utype, class_parser.Positional) = None, m: (str, io.Utype) = "get"):
        io.set_from_args(app, locals(), (io.Utype,))
        io.Super(app).__init__()

if __name__ == "__main__":
    io.ioConf.run(Main(**class_parser.Parser(Main, io.Utype).args()).runner())