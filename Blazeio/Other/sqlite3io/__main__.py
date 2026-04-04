# ./Other/sqlite3io/__main__.py
# Blazeio utilities
import Blazeio as io

try:
    from socket import SO_REUSEPORT
except ImportError:
    SO_REUSEPORT = None

io.Scope.Sql = io.createScope("\x7015")

import Blazeio.Other.Apps.Middleware.request_form as request_form
import Blazeio.Other.aws_s3 as aws_s3
import Blazeio.Other.class_parser as class_parser
import sqlite3

io.INBOUND_CHUNK_SIZE, io.OUTBOUND_CHUNK_SIZE = 1024*100, 1024*100
io.Scope.Sql.add_imports(globals())

io.Scope.Sql.web = io.App("0.0.0.0", 7015, with_keepalive = True)

class App:
    __slots__ = ("signature_key",)
    middleware = io.ddict(
        request_form = io.Scope.Sql.web.attach(request_form.RequestModel())
    )

    def __init__(app, signature_key: (str, io.Utype, class_parser.Positional) = None):
        app.signature_key = signature_key

io.Scope.Sql.App = App(**io.Scope.Sql.class_parser.Parser(App, io.Utype).args())

from .Modules.server import *

if io.is_on_render():
    from Blazeio.Modules.onrender import RenderFreeTierPatch
    io.Scope.Sql.web.attach(RenderFreeTierPatch())

io.TCPOptimizer(io.Scope.Sql.web)

if SO_REUSEPORT:
    io.Scope.Sql.web.sock().setsockopt(io.SOL_SOCKET, SO_REUSEPORT, 1)

if __name__ == "__main__":
    if io.is_on_render():
        from Blazeio.Modules.onrender import RenderFreeTierPatch
        io.Scope.web.attach(RenderFreeTierPatch())

    with io.Scope.Sql.web as web:
        web.runner()
else:
    io.create_task(io.Scope.Sql.web.run())
