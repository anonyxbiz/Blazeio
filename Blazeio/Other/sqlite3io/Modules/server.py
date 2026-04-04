# ./Other/sqlite3io/Modules/server.py
import Blazeio as io
from os import remove

@io.Scope.Sql.web.attach
class Server:
    signature_key = "X-sqlliteio-hmac-sha256"
    sqlliteio_db_path_key = "X-sqlliteio-db-path"
    conns = io.ddict()
    cond = io.ioCondition()
    def __init__(app):
        ...

    def mux(app, delimiter, data):
        return b"%b%X%b%b" % (delimiter, len(data), delimiter, data.encode())

    @io.Scope.Sql.App.middleware.request_form("form", q = io.ddict(type = str), parameters = io.ddict(type = list, default = []))
    async def _execute(app, r: io.BlazeioProtocol):
        if not (signature := r.headers.get(app.signature_key)):
            raise io.Abort("signature is required but its missing", 401)

        elif signature != io.Scope.Sql.App.signature_key:
            raise io.Abort("Invalid signature", 401)

        if not (sqlliteio_db_path := r.headers.get(app.sqlliteio_db_path_key)):
            raise io.Abort("sqlliteio_db_path is required but its missing", 401)

        if not (conn := app.conns.get(sqlliteio_db_path)):
            async with app.cond:
                if not (conn := app.conns.get(sqlliteio_db_path)):
                    app.conns[sqlliteio_db_path] = (conn := io.Scope.Sql.sqlite3.connect(sqlliteio_db_path))
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA synchronous = NORMAL;")

        await r.prepare({"Transfer-encoding": "chunked"}, 200) # Crucial to respond first

        delimiter = str(r.headers.get("Delimiter", "\x15")).encode()

        args = [r.form.q]
        
        if r.form.parameters:
            args.append(r.form.parameters)

        try:
            cursor = conn.cursor()
            cursor.execute(*tuple(args))
        except Exception as e:
            raise io.Eof(await r.write(app.mux(delimiter, io.dumps(io.ddict(error = str(e))))))

        if not cursor.description:
            conn.commit()
            raise io.Eof(await r.write(app.mux(delimiter, io.dumps(io.ddict(success = True)))))

        columns = [col[0] for col in cursor.description]

        for row in cursor:
            await r.write(app.mux(delimiter, io.dumps(dict(zip(columns, row)))))

    @io.Scope.Sql.App.middleware.request_form("form", signature = io.ddict(type = str), file = io.ddict(type = str))
    async def _backup(app, r: io.BlazeioProtocol):
        if r.form.signature != io.Scope.Sql.App.signature_key:
            raise io.Abort("Invalid signature", 401)

        if not io.path.exists(r.form.file):
            raise io.Abort("Not found", 403)
        
        async with io.Simpleserve(r, r.form.file) as f:
            await r.prepare(f.headers, f.status)
            async for chunk in f:
                await r.write(chunk)

    @io.Scope.Sql.App.middleware.request_form("form", signature = io.ddict(type = str), url = io.ddict(type = str), file = io.ddict(type = str))
    async def _upload(app, r: io.BlazeioProtocol):
        if r.form.signature != io.Scope.Sql.App.signature_key:
            raise io.Abort("Invalid signature", 401)

        async with io.getSession.get(r.form.url, follow_redirects = True) as resp:
            if not resp.ok(): raise io.Abort(await resp.text(), resp.status_code)
            await resp.save(r.form.file)

        await io.Deliver.text("Ok")

if __name__ == "__main__": ...