# ./Other/sqlite3io/Modules/server.py
import Blazeio as io

@io.Scope.Sql.instantiate
class Auth:
    __slots__ = ("routes",)
    def __init__(app):
        app.routes = io.ddict()

    def require(app, route: str):
        def wrapper(fn):
            return fn
        
        app.routes[route] = True

        return wrapper

    async def before_middleware(app, r: io.BlazeioProtocol):
        if r.path not in app.routes: return

        if not (signature_hash := r.headers.get(io.Scope.Sql.App.signature_hash_header)):
            raise io.Abort("signature hash is required but its missing", 401)

        if not io.Scope.Sql.Server.signature_client.verify(signature_hash, str(io.Scope.Sql.Server.signature_client.get_current_timestamp()).encode()):
            raise io.Abort("Signature hash did not match computed hash", 401)

@io.Scope.Sql.instantiate
class Events:
    __slots__ = ("events",)
    def __init__(app):
        app.events = io.ddict()
        app.events.writes = io.SharpEvent()
        io.Scope.Sql.web.attach(app)

    def add_event(app, form: io.ddict, cursor):
        if not int(cursor.rowcount): return
        app.events.writes.set(io.ddict(q = form.q, parameters = form.parameters, changed_rows = cursor.rowcount, lastrowid = cursor.lastrowid))

    @io.Scope.Sql.Auth.require("/events/await")
    async def _events_await(app, r: io.BlazeioProtocol):
        await io.Scope.Sql.Auth.before_middleware(r)
        if not (form := await r.json()).get("q"): raise io.Abort("q is required but its missing", 403)

        async with io.Scope.Sql.ServerParser(r) as parser:
            while 1:
                event = await app.events.writes.wait_clear()

                if not event or not isinstance(event, dict) or not event.q.startswith(form.q): continue

                await parser.write(io.dumps(event, indent=0))

@io.Scope.Sql.instantiate
class Server:
    __slots__ = ("Sql", "conns", "cond", "signature_client", "conn_ids")
    accept_methods: tuple = ("POST", "PUT")
    commit_frequency: int = (60**2)
    max_conns = 10
    def __init__(app):
        app.conn_ids = 0
        app.Sql = io.Scope.Sql
        app.conns = io.ddict()
        app.cond = io.ioCondition()
        app.signature_client = app.Sql.SignatureClient(app.Sql.App.secret_key)
        io.Scope.Sql.web.on_exit_middleware(app.on_exit)
        io.Scope.Sql.web.attach(app)
        io.Scope.Sql.web.create_task_on_start(app.commit_daemon())
    
    def get_conn_key(app, sqlliteio_db_path):
        if app.conn_ids >= app.max_conns:
            app.conn_ids = 0
        
        app.conn_ids += 1
        return "%s:%s" % (app.conn_ids, sqlliteio_db_path)

    async def commit_conns(app):
        async with app.cond:
            for conn in list(app.conns.values()):
                conn.commit()

    async def commit_daemon(app):
        async for i in io.ayield(io.Scope.Sql.App.commit_frequency):
            await app.commit_conns()

    async def on_exit(app, conns: list = []):
        await io.plog.b_green("sqlite3io", "exiting safely...")
        async with app.cond:
            pending_conns = []

            for db_path in (conns or list(app.conns.keys())):
                if not (conn := app.conns.pop(db_path, None)): 
                    continue

                await io.plog.b_green("sqlite3io", "saving and closing database (%s)..." % db_path)
            
                try:
                    await conn.commit()
                except:
                    pass

                try:
                    cursor = await conn.cursor()
                    await cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")

                    await io.plog.b_green("sqlite3io", "Checkpoint(%s) result: %s" % (db_path, cursor.fetchone()))
                    
                    await cursor.execute("PRAGMA synchronous = FULL;")
                    await cursor.execute("PRAGMA optimize;")
                    await conn.commit()
                    await cursor.execute("PRAGMA wal_checkpoint;")
                    await conn.close()
                except io.Scope.Sql.sqlite3.Error as e:
                    await io.plog.b_red("sqlite3io", "an error occurred", e)
                    pending_conns.append(conn)

            if pending_conns:
                await io.sleep(0.5)
                return await app.on_exit(pending_conns)

        await io.plog.b_green("sqlite3io", "exited safely...")

    def mux(app, delimiter, data):
        return b"%b%X%b%b" % (delimiter, len(data), delimiter, data.encode())

    async def get_json(app, r: io.BlazeioProtocol):
        if r.method not in app.accept_methods:
            raise io.Abort("Unacceptable request method", 403)

        if (signature_hash := r.headers.get(app.Sql.App.signature_hash_header, None)) is None: 
            raise io.Abort("signature hash is required but its missing", 401)

        payload = bytearray()

        async for chunk in r.pull():
            payload.extend(chunk)
            if len(payload) >= app.Sql.App.max_request_body_size:
                raise io.Abort("request payload exceeded the set maximum", 403)
        
        if not app.signature_client.verify(signature_hash, payload):
            raise io.Abort("Signature hash did not match computed hash", 401)

        try:
            if not (form := io.ddict(io.loads(payload.decode("utf-8")))).get("q"):
                raise io.Abort("q is required but its missing", 403)

            elif not isinstance(form.get("parameters"), list):
                raise io.Abort("parameters must be a list", 403)

            query = io.ddict(form = form)

            if not (sqlliteio_db_path := r.headers.get(app.Sql.App.sqlliteio_db_path_header)):
                raise io.Abort("sqlliteio_db_path header is required but its missing", 401)
            
            if not (conn := app.conns.get(app.get_conn_key(sqlliteio_db_path))):
                conn = await app.get_or_create_conn(r, sqlliteio_db_path)

            query.args, query.sqlliteio_db_path, query.conn, query.cursor, query.delimiter = [form.q], sqlliteio_db_path, conn, await conn.cursor(), str(r.headers.get(app.Sql.App.sqlliteio_delimiter_header, "\x15")).encode()
            query.args.append(form.parameters)
            
            return query

        except io.JSONDecodeError:
            raise io.Abort("No valid JSON found in the stream.", 403)

    async def get_or_create_conn(app, r: io.BlazeioProtocol, sqlliteio_db_path: str):
        async with app.cond:
            if (conn := app.conns.get(app.get_conn_key(sqlliteio_db_path))):
                return conn

            app.conns[app.get_conn_key(sqlliteio_db_path)] = (conn := app.Sql.asqlite3.connect(sqlliteio_db_path))
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA synchronous = NORMAL;")
            await conn.execute("PRAGMA busy_timeout = 30000;")
            await conn.execute("PRAGMA temp_store = MEMORY;")

            if app.Sql.App.connection_commands:
                for i in app.Sql.App.connection_commands.split(";"):
                    await conn.execute("%s;" % i)

        return conn

    async def _execute(app, r: io.BlazeioProtocol):
        query = await app.get_json(r)
        
        async with app.cond:
            ...

        await r.prepare({"Transfer-encoding": "chunked", "Content-type": "video/mp4", "Cache-Control": "no-store, no-cache, must-revalidate, private", "Cloudflare-CDN-Cache-Control": "no-store, no-cache", "Pragma": "no-cache", "X-Accel-Buffering": "no"}, 200)

        try:
            await query.cursor.execute(*tuple(query.args))
        except Exception as e:
            raise io.Eof(await r.write(app.mux(query.delimiter, io.dumps(io.ddict(error = str(e))))))
 
        if not query.cursor.description:
            io.Scope.Sql.Events.add_event(query.form, query.cursor)
            raise io.Eof(await r.write(app.mux(query.delimiter, io.dumps(io.ddict(success = True)))), io.Scope.Sql.Events.add_event(query.form, query.cursor))

        columns = [col[0] for col in query.cursor.description]

        async for row in query.cursor:
            await r.write(app.mux(query.delimiter, io.dumps(dict(zip(columns, row)))))

    async def _executemany(app, r: io.BlazeioProtocol):
        query = await app.get_json(r)

        async with app.cond:
            ...

        await r.prepare({"Transfer-encoding": "chunked", "Content-type": "video/mp4", "Cache-Control": "no-store, no-cache, must-revalidate, private", "Cloudflare-CDN-Cache-Control": "no-store, no-cache", "Pragma": "no-cache", "X-Accel-Buffering": "no"}, 200)
        
        try:
            await query.cursor.executemany(*tuple(query.args))
        except Exception as e:
            raise io.Eof(await r.write(app.mux(query.delimiter, io.dumps(io.ddict(error = str(e))))))
    
        if not query.cursor.description:
            io.Scope.Sql.Events.add_event(query.form, query.cursor)
            raise io.Eof(await r.write(app.mux(query.delimiter, io.dumps(io.ddict(success = True)))), io.Scope.Sql.Events.add_event(query.form, query.cursor))

        columns = [col[0] for col in query.cursor.description]

        async for row in query.cursor:
            await r.write(app.mux(query.delimiter, io.dumps(dict(zip(columns, row)))))

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