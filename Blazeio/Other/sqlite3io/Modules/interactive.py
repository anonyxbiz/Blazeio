# ./Other/sqlite3io/Modules/interactive.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser
import Blazeio.Other.sqlite3io.Modules.client as sql_client

io.Scope.add_imports(globals())

class App:
    __slots__ = ("secret_key", "server_addr", "file", "queries", "db",)
    def __init__(app, secret_key: (str, io.Utype, class_parser.Positional) = None, server_addr: (str, io.Utype, class_parser.Positional) = None, file: (str, io.Utype, class_parser.Positional) = None, queries: (str, io.Utype, class_parser.Positional) = None):
        io.set_from_args(app, locals(), io.Utype)
        app.db = sql_client.SqlSession("%s/execute" % app.server_addr, app.secret_key, app.file)
        io.ioConf.run(app.start())

    async def start(app):
        for query in app.queries.split(";"):
            if not query: continue
            async for row in app.db.ajson(query):
                await io.plog.b_green(io.dumps(row, indent=1))

if __name__ == "__main__":
    App(**io.Scope.class_parser.Parser(App, io.Utype).args())