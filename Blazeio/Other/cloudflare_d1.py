# Blazeio.Other.cloudflare_d1
import Blazeio as io

class SqlError(io.Err):
    ...

class Client:
    __slots__ = ("account_id", "database_id", "headers", "schema", "result_only", "retries", "endpoint", "table_checks_completion_event")
    base_url = "https://api.cloudflare.com/client/v4"
    sql_paths = ("query",)
    def __init__(app, account_id: str, database_id: str, headers: dict, schema: (None, dict) = None, result_only: bool = True, retries: int = 3):
        io.set_from_args(app, locals(), (str, int, dict, bool, None))
        app.table_checks_completion_event = io.SharpEvent()
        app.endpoint = "%s/accounts/%s/d1/database/%s" % (app.base_url, app.account_id, app.database_id)
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

    async def unique_token(app, q: str, *params, start: int = 1):
        for i in range(1, 1000):
            for o in range(start, 1*i):
                if not await app(q, *params, token := io.token_urlsafe(o)[:o]):
                    return token

    async def validate_column(app, name: str, column: str, definition: str):
        if not await app("SELECT name FROM pragma_table_info('%s') WHERE name = '%s';" % (name, column)):
            await app("ALTER TABLE %s ADD COLUMN %s %s;" % (name, column, definition))

    async def check_table(app, name: str, table: dict):
        tasks = []
        try:
            if table.get("drop"):
                await app("DROP TABLE IF EXISTS %s;" % name)

            if isinstance(await app("SELECT name FROM sqlite_master WHERE type='table' AND name='%s';" % name), dict):
                tasks.extend([io.create_task(app.validate_column(name, column, value)) for column, value in table.get("columns").items()])
            else:
                await app(cmd := "CREATE TABLE IF NOT EXISTS %s (%s%s);" % (name, (", ".join(["%s %s" % (key, value) for key, value in table.get("columns").items()])), ", " + ", ".join(list(table.get("commands"))) if table.get("commands") else ""))

                if table.get("create_index"):
                    await app("CREATE INDEX idx_%s ON %s (%s);" % (name, name, ", ".join(list(table.get("columns").keys()))))
        finally:
            if tasks: return await io.gather(*tasks)

    async def initialize(app):
        if not app.schema: return
        tasks = []
        try:
            for name, table in app.schema.get("tables").items():
                tasks.append(io.create_task(app.check_table(name, table)))
        finally:
            try:
                if tasks: await io.gather(*tasks)
            finally:
                app.table_checks_completion_event.set()

    async def sql(app, path: str, cmd: str, *params, data_type: (dict, list) = dict, batch: bool = False):
        retries = app.retries
        while (retries := retries-1) >= 1:
            try:
                async with io.getSession.post(app.endpoint + path, app.headers, json = io.ddict(sql = cmd, params = list(params), batch = batch)) as resp:
                    data = await resp.json()

                    if (result := data.get("result")) and (results := result[0].get("results")):
                        return results if (len(results) > 1 or data_type == list) else io.ddict(results[0])

                    if not app.result_only:
                        return result
                    else:
                        return []

            except io.ServerDisconnected:
                continue

            break

if __name__ == "__main__":
    ...