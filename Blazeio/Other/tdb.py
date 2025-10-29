# Blazeio.Other.tdb
import Blazeio as io
from Blazeio.Other.crypto import Ciphen

class Tdb:
    __slots__ = ("file", "db", "loaded", "cond", "cipher", "tasks", "load_db")
    def __init__(app, file: str, cipher_key: str, db: dict = {}, load_db: bool = True):
        object.__setattr__(app, "file", file)
        object.__setattr__(app, "tasks", [])
        object.__setattr__(app, "db", io.Dotify(db))
        object.__setattr__(app, "loaded", io.SharpEvent())
        object.__setattr__(app, "cond", io.ioCondition())
        object.__setattr__(app, "cipher", Ciphen(cipher_key))
        object.__setattr__(app, "load_db", load_db)
        app.tasks.append(io.getLoop.create_task(app.daemon()))

    def __getattr__(app, key):
        return app.db[key]

    def __setattr__(app, key, value):
        app.db[key] = value

    async def __aenter__(app):
        await app.cond.__aenter__()
        return app

    async def __aexit__(app, *args):
        return await app.cond.__aexit__(*args)

    def get_bytes(app):
        return io.dumps(io.ensure_dumpable(io.ddict(app.db)), indent=0).encode()

    async def daemon(app):
        async with io.Ehandler(exit_on_err = 1, ignore = io.CancelledError):
            if app.load_db and io.path.exists(app.file):
                json_data = await io.aread(app.file)
                try:
                    json_data = io.loads(app.cipher.decrypt(json_data))
                except io.JSONDecodeError:
                    json_data = io.loads(json_data)

                app.db.update(io.Dotify(json_data))

            app.loaded.set()

            previous_json = app.get_bytes()

            while True:
                await app.cond.on_acquire_change()

                if (json := app.get_bytes()) != previous_json:
                    await io.asave(app.file, app.cipher.encrypt(json))

                previous_json = json

if __name__ == "__main__": ...