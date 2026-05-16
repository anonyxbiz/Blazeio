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
from .Modules.security import SignatureClient

import sqlite3

io.Scope.Sql.add_imports(globals())

class App:
    __slots__ = ("secret_key", "server_port", "server_buffer_size", "max_request_body_size", "middleware", "secret_key_header", "sqlliteio_db_path_header", "signature_hash_header", "sqlliteio_delimiter_header")
    def __init__(app, secret_key: (str, io.Utype, class_parser.Positional) = None, server_port: (int, io.Utype) = 7015, server_buffer_size: (int, io.Utype) = 1024*10, max_request_body_size: (int, io.Utype) = 1024*100, secret_key_header: (str, io.Utype) = "X-sqlliteio-hmac-sha256", signature_hash_header: (str, io.Utype) = "X-sqlliteio-hmac-sha256-hash", sqlliteio_db_path_header: (str, io.Utype) = "X-sqlliteio-db-path", sqlliteio_delimiter_header: (str, io.Utype) = "X-sqlliteio-delimiter"):
        io.set_from_args(app, locals(), io.Utype)
        app.init_server()

    def init_server(app):
        io.INBOUND_CHUNK_SIZE, io.OUTBOUND_CHUNK_SIZE = app.server_buffer_size, app.server_buffer_size
        io.Scope.Sql.web = io.App("0.0.0.0", app.server_port, with_keepalive = True)
        app.init_on_render()
        app.init_tcp_optimizer()
        app.init_reuse_port()
        app.init_middleware()

    def init_on_render(app):
        if io.is_on_render():
            from Blazeio.Modules.onrender import RenderFreeTierPatch
            io.Scope.Sql.web.attach(RenderFreeTierPatch())

    def init_tcp_optimizer(app):
        io.TCPOptimizer(io.Scope.Sql.web)
        
    def init_reuse_port(app):
        if SO_REUSEPORT:
            io.Scope.Sql.web.sock().setsockopt(io.SOL_SOCKET, SO_REUSEPORT, 1)

    def init_middleware(app):
        app.middleware = io.ddict(
            request_form = io.Scope.Sql.web.attach(request_form.RequestModel())
        )

io.Scope.Sql.App = App(**io.Scope.Sql.class_parser.Parser(App, io.Utype).args())

from .Modules.server import *

if __name__ == "__main__":
    if io.is_on_render():
        from Blazeio.Modules.onrender import RenderFreeTierPatch
        io.Scope.Sql.web.attach(RenderFreeTierPatch())

    with io.Scope.Sql.web as web:
        web.runner()
else:
    io.create_task(io.Scope.Sql.web.run())
