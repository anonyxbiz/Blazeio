# __main__.py
import Blazeio as io
import Blazeio.Other.Apps.Middleware.request_form as request_form

io.ioConf.INBOUND_CHUNK_SIZE, io.ioConf.OUTBOUND_CHUNK_SIZE = 1024*10, 1024*10

io.Scope.add_imports(globals())

io.Scope.web = io.App("0.0.0.0", 8005, with_keepalive = True)

@io.Scope
class App:
    middleware = io.ddict(
        request_form = io.Scope.web.attach(request_form.RequestModel())
    )

from .Modules import app

if __name__ == "__main__":
    io.TCPOptimizer(io.Scope.web)

    with io.Scope.web:
        io.Scope.web.runner()