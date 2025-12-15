# Blazeio.Other.cloudflare_d1
import Blazeio as io

class Client:
    __slots__ = ("account_id", "database_id", "headers", "schema", "result_only", "endpoint")
    base_url = "https://api.cloudflare.com/client/v4"
    sql_paths = ("query",)
    def __init__(app, account_id: str, database_id: str, headers: dict, schema: (None, dict) = None, result_only: bool = True):
        io.set_from_args(app, locals(), (str, dict, bool, None))
        app.endpoint = "%s/accounts/%s/d1/database/%s" % (app.base_url, app.account_id, app.database_id)
        io.create_task(app.initialize())

    def __getattr__(app, key: str):
        if key not in app.sql_paths: raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, key))

        def method(*args, **kwargs): return app.sql("/%s" % key, *args, **kwargs)

        method.__name__ = key
        return method
    
    async def validate_column(app, name: str, column: str, definition: str):
        if not await app.query("SELECT name FROM pragma_table_info('%s') WHERE name = '%s';" % (name, column)):
            await app.query("ALTER TABLE %s ADD COLUMN %s %s;" % (name, column, definition))

    async def initialize(app):
        if not app.schema: return
        tasks = []
        try:
            for name, table in app.schema.get("tables").items():
                if table.get("drop"):
                    await app.query("DROP TABLE IF EXISTS %s;" % name)
                if await app.query("SELECT name FROM sqlite_master WHERE type='table' AND name='%s';" % name):
                    tasks.extend([io.create_task(app.validate_column(name, column, value)) for column, value in table.get("columns").items()])
                else:
                    tasks.append(io.create_task(app.query("CREATE TABLE IF NOT EXISTS %s (%s%s);" % (name, (", ".join(["%s %s" % (key, value) for key, value in table.get("columns").items()])), ", " + ", ".join(list(table.get("commands"))) if table.get("commands") else ""))))

                    if table.get("create_index"):
                        tasks.append(io.create_task(app.query("CREATE INDEX idx_%s ON %s (%s);" % (name, name, ", ".join(list(table.get("columns").keys()))))))
        finally:
            if tasks: await io.gather(*tasks)

    async def sql(app, path: str, cmd: str, *params):
        async with io.getSession.post(app.endpoint + path, app.headers, json = io.ddict(sql = cmd, params = list(params))) as resp:
            data = await resp.json()
            if (result := data.get("result")) and (results := result[0].get("results")):
                return results if len(results) > 1 else io.ddict(results[0])

            if not app.result_only:
                return result

if __name__ == "__main__":
    ...