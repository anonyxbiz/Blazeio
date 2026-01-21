# Blazeio.Other.cloudflare_d1
import Blazeio as io

class SqlError(io.Err):
    ...

class RetryError(io.Err):
    ...

class Response:
    __slots__ = ()

    async def stream(app, cmd: str, *params, data_type: (dict, list) = dict, batch: bool = False):
        retries = app.retries
        while (retries := retries-1) >= 1:
            try:
                async with io.getSession.post(app.endpoint + "/query", app.headers, json = io.ddict(sql = cmd, params = list(params), batch = batch)) as resp:
                    async for chunk in resp:
                        yield chunk

            except io.ServerDisconnected:
                continue

            break

class StreamTo:
    __slots__ = ("db", "stream", "headers", "status_code")
    def __init__(app, db, stream: io.BlazeioProtocol, headers: dict = {}, status_code: (int, None) = None):
        app.db, app.stream, app.headers, app.status_code = db, stream, io.ddict(headers), status_code

    def __call__(app, *args, **kwargs):
        return app.stream_into(*args, **kwargs)

    async def stream_into(app, cmd: str, *params, **kwargs):
        retries = app.db.retries
        while (retries := retries-1) >= 1:
            try:
                async with io.getSession.post(app.db.endpoint + "/query", app.db.headers, json = io.ddict(sql = cmd, params = list(params), **kwargs)) as resp:
                    app.headers["Content-type"] = resp.content_type
                    
                    if not app.stream.__is_prepared__:
                        await app.stream.prepare({**io.Ctypes.chunked, **app.headers}, app.status_code if app.status_code is not None else resp.status_code)

                    async for chunk in resp:
                        await app.stream.write(chunk)

                    await app.stream.eof()

            except io.ServerDisconnected:
                continue

            break

class Client(Response):
    __slots__ = ("account_id", "database_id", "headers", "schema", "result_only", "retries", "endpoint", "table_checks_completion_event", "log", "on_creation_queries")
    base_url = "https://api.cloudflare.com/client/v4"
    sql_paths = ("query",)
    def __init__(app, account_id: str, database_id: str, headers: dict, schema: (None, dict) = None, result_only: bool = True, retries: int = 5, log: bool = False):
        io.set_from_args(app, locals(), (str, int, dict, bool, None))
        app.on_creation_queries = []
        app.table_checks_completion_event = io.SharpEvent()
        app.endpoint = "%s/accounts/%s/d1/database/%s" % (app.base_url, app.account_id, app.database_id)
        if app.schema: app.prepare_tables()
        io.create_task(app.initialize())

    @property
    def __name__(app):
        return "Client"
    
    def __await__(app):
        yield from app.table_checks_completion_event.wait().__await__()
        return

    def __call__(app, *args, **kwargs):
        return app.sql("/query", *args, **kwargs)

    def query(app, *args, **kwargs):
        return app.sql("/query", *args, **kwargs)

    def stream_to(app, *args, **kwargs):
        return StreamTo(app, *args, **kwargs)
        
    def prepare_tables(app):
        for name, table in app.schema.get("tables").items():
            if not table.get("sql"):
                table["sql"] = "CREATE TABLE %s (%s%s)" % (name, (", ".join(["%s %s" % (key, value) for key, value in table.get("columns").items()])), ", " + ", ".join(list(table.get("commands"))) if table.get("commands") else "")

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
    
    async def checker(app, cmd: str, *args, **kwargs):
        if app.log:
            await io.plog.yellow(cmd)

        result = await app(cmd, *args, **kwargs)

        if app.log:
            await io.plog.yellow(io.dumps(result))
        
        return result
    
    async def sync_tables(app):
        return {i.get("name"): i for i in await app.checker("; ".join(["SELECT * FROM sqlite_master WHERE type='table' AND name='%s';" % name for name, table in app.schema.get("tables").items()]), data_type = list) if i}

    async def check_tables(app):
        if (drops := ["DROP TABLE IF EXISTS %s" % name for name, table in app.schema.get("tables").items() if table.get("drop")]):
            await app.checker("; ".join(drops))

        results = await app.sync_tables()

        queries = []

        for name, table in app.schema.get("tables").items():
            if not (result := results.get(name)):
                queries.append(table.get("sql"))
                if table.get("create_index"):
                    queries.append("CREATE INDEX idx_%s ON %s (%s)" % (name, name, ", ".join(list(table.get("columns").keys()))))

                if (on_creation_queries := table.get("on_creation_queries")):
                    app.on_creation_queries.append(on_creation_queries)

            elif result.get("sql") != table.get("sql"):
                for column, definition in table.get("columns").items():
                    if "%s %s" % (column, definition) not in result.get("sql"):
                        queries.append("ALTER TABLE %s ADD COLUMN %s %s" % (name, column, definition))
        
        if queries and not (result := await app.checker(query := "; ".join(queries), raw_response = True)).get("success"):
            await io.plog.b_red(io.dumps(io.ddict(query = query, result = result)))

        if app.on_creation_queries:
            if not (result := await app.checker(query := "; ".join(app.on_creation_queries), raw_response = True)).get("success"):
                await io.plog.b_red(io.dumps(io.ddict(query = query, result = result)))

    async def initialize(app):
        if not app.schema: return
        try:
            await app.check_tables()
        finally:
            app.table_checks_completion_event.set()

    async def sql(app, path: str, cmd: str, *params, data_type: (dict, list) = dict, raw_response: bool = False, **kwargs):
        retries = app.retries
        while (retries := retries-1) >= 1:
            try:
                async with io.getSession.post(app.endpoint + path, app.headers, json = io.ddict(sql = cmd, params = list(params), **kwargs)) as resp:
                    try:
                        data = await resp.json()
                    except io.JSONDecodeError:
                        if cmd.startswith("SELECT"): continue
                        raise

                    if raw_response: return data

                    if not (result := data.get("result")):
                        if (errors := data.get("errors")) and errors[0].get("message") == "D1 DB storage operation exceeded timeout which caused object to be reset.": continue

                        return result

                    elif len(result) > 1:
                        results = [rs[0] if len(rs := i.get("results")) == 1 else rs for i in result]
                    else:
                        if len(results := result[0].get("results")) == 1 and data_type != list:
                            results = io.ddict(results[0])

                    return results

            except io.ServerDisconnected:
                continue

            break

if __name__ == "__main__":
    ...