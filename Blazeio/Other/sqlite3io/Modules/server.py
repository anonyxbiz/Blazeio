# ./Other/sqlite3io/Modules/server.py
import Blazeio as io

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

if __name__ == "__main__": ...