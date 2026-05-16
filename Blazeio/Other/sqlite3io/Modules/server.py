# ./Other/sqlite3io/Modules/server.py
import Blazeio as io

@io.Scope.Sql.web.attach
class Server:
    __slots__ = ("Sql", "conns", "cond", "signature_client")
    accept_methods: tuple = ("POST", "PUT")
    def __init__(app):
        app.Sql = io.Scope.Sql
        app.conns = io.ddict()
        app.cond = io.ioCondition()
        app.signature_client = app.Sql.SignatureClient(app.Sql.App.secret_key)

    def mux(app, delimiter, data):
        return b"%b%X%b%b" % (delimiter, len(data), delimiter, data.encode())

    async def get_json(app, r: io.BlazeioProtocol):
        if r.method not in app.accept_methods:
            raise io.Abort("Unacceptable request method", 403)

        if not (signature_hash := r.headers.get(app.Sql.App.signature_hash_header)):
            raise io.Abort("signature hash is required but its missing", 401)

        payload = bytearray()

        async for chunk in r.pull():
            payload.extend(chunk)
            if len(payload) >= app.Sql.App.max_request_body_size:
                raise io.Abort("request payload exceeded the set maximum", 403)
        
        if not app.signature_client.verify(signature_hash, payload):
            raise io.Abort("Signature hash did not match computed hash", 401)

        try:
            return io.ddict(io.loads(payload.decode("utf-8")))
        except io.JSONDecodeError:
            raise io.Abort("No valid JSON found in the stream.", 403)
    
    async def get_or_create_conn(app, sqlliteio_db_path: str):
        async with app.cond:
            if (conn := app.conns.get(sqlliteio_db_path)):
                return conn

            app.conns[sqlliteio_db_path] = (conn := app.Sql.sqlite3.connect(sqlliteio_db_path))
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")

        return conn

    async def _execute(app, r: io.BlazeioProtocol):
        if not (form := await app.get_json(r)).get("q"):
            raise io.Abort("q is required but its missing", 403)

        elif not isinstance(form.get("parameters"), list):
            raise io.Abort("parameters must be a list", 403)

        if not (sqlliteio_db_path := r.headers.get(app.Sql.App.sqlliteio_db_path_header)):
            raise io.Abort("sqlliteio_db_path header is required but its missing", 401)

        if not (conn := app.conns.get(sqlliteio_db_path)):
            conn = await app.get_or_create_conn(sqlliteio_db_path)

        await r.prepare({"Transfer-encoding": "chunked", "Content-type": "video/mp4", "Cache-Control": "no-store, no-cache, must-revalidate, private", "Cloudflare-CDN-Cache-Control": "no-store, no-cache", "Pragma": "no-cache", "X-Accel-Buffering": "no"}, 200) # Proxies should not transform data

        delimiter = str(r.headers.get(app.Sql.App.sqlliteio_delimiter_header, "\x15")).encode()

        args = [form.q]

        if form.parameters:
            args.append(form.parameters)

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
        if r.form.signature != app.Sql.App.secret_key:
            raise io.Abort("Invalid secret key", 401)

        if not io.path.exists(r.form.file):
            raise io.Abort("Not found", 403)

        async with io.Simpleserve(r, r.form.file) as f:
            await r.prepare(f.headers, f.status)
            async for chunk in f:
                await r.write(chunk)

    @io.Scope.Sql.App.middleware.request_form("form", signature = io.ddict(type = str), url = io.ddict(type = str), file = io.ddict(type = str))
    async def _upload(app, r: io.BlazeioProtocol):
        if r.form.signature != app.Sql.App.secret_key:
            raise io.Abort("Invalid signature", 401)

        async with io.getSession.get(r.form.url, follow_redirects = True) as resp:
            if not resp.ok(): raise io.Abort(await resp.text(), resp.status_code)
            await resp.save(r.form.file)

        await io.Deliver.text("Ok")

if __name__ == "__main__": ...