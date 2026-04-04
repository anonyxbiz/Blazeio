# ./Other/sqlite3io/Modules/client.py
import Blazeio as io

class StreamTo:
    __slots__ = ("session", "stream", "headers", "status_code")
    def __init__(app, session, stream: io.BlazeioProtocol, headers: dict = {}, status_code: (int, None) = 200):
        app.session, app.stream, app.headers, app.status_code = session, stream, io.ddict(headers), status_code

    def __call__(app, *args, **kwargs):
        return app.stream_into(*args, **kwargs)

    async def stream_into(app, cmd: str, *params, **kwargs):
        app.headers["Content-type"] = "application/json"
        app.headers["Transfer-encoding"] = "chunked"

        if not app.stream.__is_prepared__:
            await app.stream.prepare(app.headers, app.status_code)

        return await app.session.pipe_to(app.stream, cmd, *params, **kwargs)

class Parser:
    __slots__ = ("prot", "buff", "size")
    delimiter: bytes = b"\x15"
    def __init__(app, prot):
        app.prot, app.buff, app.size = prot, bytearray(), None

    def parse(app):
        if app.size is None:
            if (idx := app.buff.find(app.delimiter)) == -1: return

            buff = app.buff[idx + len(app.delimiter):]

            if (idx := buff.find(app.delimiter)) == -1: return

            app.size, app.buff = int(buff[:idx], 16), buff[idx + len(app.delimiter):]

        if len(app.buff) < app.size: return

        chunk, app.buff, app.size = bytes(app.buff[:app.size]), app.buff[app.size:], None

        return chunk

    async def __aiter__(app):
        async for chunk in app.prot:
            app.buff.extend(chunk)
            while (chunk := app.parse()): yield chunk

class SqlSession:
    __slots__ = ("url", "conn", "schema", "signature_key", "sqlliteio_db_path", "table_checks_completion_event")
    def __init__(app, url: str, signature_key: str, sqlliteio_db_path: str, schema: dict = {}):
        io.set_from_args(app, locals(), (str, bool, dict))
        app.table_checks_completion_event = io.SharpEvent()
        if app.schema: app.prepare_tables()

    def prepare_tables(app):
        for name, table in app.schema.get("tables").items():
            if not table.get("sql"):
                table["sql"] = "CREATE TABLE %s (%s%s)" % (name, (", ".join(["%s %s" % (key, value) for key, value in table.get("columns").items()])), ", " + ", ".join(list(table.get("commands"))) if table.get("commands") else "")

    async def checker(app, cmd: str, *args, **kwargs):
        return await app(cmd, *args, **kwargs)

    async def sync_tables(app):
        sqlite_master = [await app("SELECT * FROM sqlite_master WHERE type='table' AND name='%s';" % name) for name, table in app.schema.get("tables").items()]
        return {i.get("name"): i for i in sqlite_master if i}

    async def check_tables(app):
        if (drops := ["DROP TABLE IF EXISTS %s" % name for name, table in app.schema.get("tables").items() if table.get("drop")]):
            await io.gather(*[io.create_task(app.checker(i)) for i in drops])

        if (results := await app.sync_tables()):
            ...
        else:
            await io.plog.b_red("No tables found!")

        queries, on_creation_queries_batch = [], []

        for name, table in app.schema.get("tables").items():
            if not (result := results.get(name)):
                queries.append(table.get("sql"))
                if table.get("create_index"):
                    queries.append("CREATE INDEX idx_%s ON %s (%s)" % (name, name, ", ".join(list(table.get("columns").keys()))))

                if (on_creation_queries := table.get("on_creation_queries")):
                    on_creation_queries_batch.extend(on_creation_queries) if isinstance(on_creation_queries, list) else on_creation_queries_batch.append(on_creation_queries)

            elif result.get("sql") != table.get("sql"):
                for column, definition in table.get("columns").items():
                    if "%s %s" % (column, definition) not in result.get("sql"):
                        queries.append("ALTER TABLE %s ADD COLUMN %s %s" % (name, column, definition))
        
        for batch in (queries, on_creation_queries_batch):
            for query in batch:
                if (result := await app(query)):
                    await io.plog.b_green(io.dumps(io.ddict(query = query, result = result)))

    async def initialize(app):
        if not app.schema: return
        try:
            await app.check_tables()
        finally:
            app.table_checks_completion_event.set()

    def __call__(app, *args, **kwargs):
        return app.json(*args, **kwargs)

    def __await__(app):
        yield from app.table_checks_completion_event.wait().__await__()
        return

    @property
    def __name__(app):
        return "SqlSession"

    @classmethod
    async def query(cls, app, *args, **kwargs):
        return await app.sql(*args, **kwargs)

    def sql(app, *args, **kwargs):
        return app.json(*args, **kwargs)

    async def json(app, *args, data_type = dict):
        data = [i if isinstance(i, dict) else io.ddict(io.loads(i.decode())) async for i in app.execute(*args)]

        return data.pop(0) if len(data) == 1 and data_type != list else data

    async def ajson(app, *args):
        async for row in app.execute(*args):
            yield io.ddict(io.loads(row.decode()))

    def stream_to(app, *args, **kwargs):
        return StreamTo(app, *args, **kwargs)

    async def unique_token(app, q: str, *params, start: int = 1):
        for i in range(1, 1000):
            for o in range(start, 1*i):
                if not await app(q, *params, token := io.token_urlsafe(o)[:o]):
                    return token

    async def unique_id(app, q: str, *params, start: int = 1):
        for i in range(1, 1000):
            for o in range(start, 1*i):
                for a in range(o):
                    if not await app(q, *params, token := str(io.uuid4())[:o]):
                        return token

    async def execute(app, q, *parameters):
        async with io.getSession.post(app.url, {"Transfer-encoding": "chunked", "X-sqlliteio-hmac-sha256": app.signature_key, "X-sqlliteio-db-path": app.sqlliteio_db_path, "Content-type": "application/json"}) as resp:
            payload = io.ddict(q = q, parameters = [])
            for i in parameters:
                if i is None:
                    i = "NULL"
                elif isinstance(i, bool):
                    i = int(i)
                payload.parameters.append(str(i))

            await resp.eof(io.dumps(payload).encode())

            await resp.prepare_http()

            if not resp.ok(): raise io.Abort(await resp.text(), resp.status_code)

            async for chunk in Parser(resp):
                yield chunk

    async def pipe_to(app, stream, *args, **kwargs):
        row_count = 0
        await stream.write(b"[\n")
        async for row in app.execute(*args, **kwargs):
            if row_count:
                row = b",\n%b" % row

            row_count += 1

            await stream.write(row)
        
        await stream.eof(b"\n]")

        return row_count

if __name__ == "__main__": ...