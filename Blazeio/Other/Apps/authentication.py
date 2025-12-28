# ./Other/Apps/Auth/authentication.py
import Blazeio as io
from hmac import new as hmac_new
from hashlib import sha1 as sha256

class Register:
    __slots__ = ()
    def __init__(app):
        @app.add_route
        def _register(r: io.BlazeioProtocol, route: str = app.schema.register.endpoint):
            return app.register(r)

    async def register(app, r: io.BlazeioProtocol):
        data = await r.body_or_params()
        
        if not (email := data.get("email")):
            raise io.Abort("email is required", 403)

        if not (username := data.get("username")):
            raise io.Abort("username is required", 403)

        if not (password := data.get("password")):
            raise io.Abort("password is required", 403)

        if await app.database("SELECT email FROM users WHERE email = ?;", data.email):
            raise io.Abort("Email already registered.", 403)

        if await app.database("SELECT username FROM users WHERE username = ?;", data.username):
            raise io.Abort("username is taken", 403)

        await app.database(
            "INSERT INTO users (email, username, password, ip) VALUES (?, ?, ?, ?);",
            email,
            username,
            io.urlsafe_b64encode(hmac_new(app.hashing_key.encode(), password.encode(), sha256).digest()).decode(),
            r.ip_host
        )

        if not await app.database("SELECT username FROM users WHERE username = ?;", username):
            raise io.Abort("Something went wrong", 500)
        
        raise io.Abort(*app.schema.login.on_successs_raise)

class Login:
    __slots__ = ()
    def __init__(app):
        @app.add_route
        def _login(r: io.BlazeioProtocol, route: str = app.schema.login.endpoint):
            return app.login(r)

    async def login(app, r: io.BlazeioProtocol):
        data = await r.body_or_params()
        if not (username := data.get("username")) or not (password := data.get("password")):
            raise io.Abort("username and password are required", 403)

        if not (user := await app.database("SELECT id FROM users WHERE username = ? AND password = ?;", username, io.urlsafe_b64encode(hmac_new(app.hashing_key.encode(), password.encode(), sha256).digest()).decode())):
            raise io.Abort("Invalid credentials", 403)

        await app.database(
            "INSERT INTO sessions (user_id, cookie, expires_at, ip) VALUES (?, ?, ?, ?);",
            user.id,
            cookie := await app.database.unique_token("SELECT cookie FROM sessions WHERE user_id = ? AND cookie = ?", user.id, start = 32),
            (expires := (io.dt.now(io.UTC) + io.timedelta(**app.schema.session.expires_after))).isoformat(),
            r.ip_host,
        )

        if not await app.database("SELECT cookie FROM sessions WHERE cookie = ?;", cookie):
            raise io.Abort("Something went wrong", 500)

        r.set_cookie(app.schema.session.cookie["name"], cookie, expires.strftime("%a, %d %b %Y %H:%M:%S UTC"), **app.schema.session.cookie["options"])

        raise io.Abort(*app.schema.login.on_successs_raise)

class Session:
    __slots__ = ()
    def __init__(app):
        ...

    async def validate_session(app, r: io.BlazeioProtocol, cookie: str):
        if (session := await app.database("SELECT u.*, s.* FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.cookie = ? AND s.expires_at > ?;", cookie, io.dt.now(io.UTC).isoformat())):
            for i in ("password", "cookie"):
                session.pop(i, None)
            r.store[app.schema.session.key] = session

    async def auth_user(app, r: io.BlazeioProtocol):
        if r.store is None:
            r.store = io.ddict()

        r.store.cookies = r.cookies()
        r.store.session = None

        if (user_cookie := r.store.cookies.get(app.schema.session.cookie["name"])):
            await app.validate_session(r, user_cookie)

        return r.store.session

    async def before_middleware(app, r: io.BlazeioProtocol):
        if not r.path in app.routes: return
        await app.auth_user(r)

        if not r.store.session:
            raise io.Abort(*app.schema.session.on_fail_raise)

class Auth(Register, Login, Session):
    __slots__ = ("database", "schema", "hashing_key", "_register", "_login")
    routes = io.Routemanager()
    def __init__(app, database, hashing_key: str, register: dict, login: dict, session: dict):
        app.database, app.hashing_key = database, hashing_key
        app.schema = io.ddict(
            register = io.ddict(register),
            login = io.ddict(login),
            session = io.ddict(session),
        )
        io.Super(app).__init__()

    @property
    def __name__(app):
        return "Auth"

    def __call__(app, *args, **kwargs):
        return app.routes.__call__(*args, **kwargs)

    def add_route(app, fn):
        object.__setattr__(app, fn.__name__, fn)
        return fn

if __name__ == "__main__": ...