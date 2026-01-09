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

        @app.add_route
        @app.routes
        def _logout(r: io.BlazeioProtocol, route: str = app.schema.logout.endpoint):
            return app.logout(r)

    async def login(app, r: io.BlazeioProtocol):
        data = await r.body_or_params()
        if not (username := data.get("username")) or not (password := data.get("password")):
            raise io.Abort("username and password are required", 403)

        if not (user := await app.database("SELECT id FROM users WHERE username = ? AND password = ?;", username, io.urlsafe_b64encode(hmac_new(app.hashing_key.encode(), password.encode(), sha256).digest()).decode())):
            raise io.Abort("Invalid credentials", 403)

        await app.database(
            "INSERT INTO sessions (user_id, cookie, expires_at, ip) VALUES (?, ?, ?, ?);",
            user.id,
            cookie := await app.database.unique_id("SELECT cookie FROM sessions WHERE user_id = ? AND cookie = ?", user.id, start = 32),
            (expires := (io.dt.now(io.UTC) + io.timedelta(**app.schema.session.expires_after))).isoformat(),
            r.ip_host,
        )

        if not await app.database("SELECT cookie FROM sessions WHERE cookie = ?;", cookie):
            raise io.Abort("Something went wrong", 500)

        r.set_cookie(app.schema.session.cookie["name"], cookie, expires.strftime("%a, %d %b %Y %H:%M:%S UTC"), **app.schema.session.cookie["options"])

        raise io.Abort(*app.schema.login.on_successs_raise)

    async def logout(app, r: io.BlazeioProtocol):
        await app.database("DELETE FROM sessions WHERE user_id = ? AND cookie = ?;", r.store[app.schema.session.key]["user_id"], r.store[app.schema.session.key]["cookie"])

        r.set_cookie(app.schema.session.cookie["name"], r.store[app.schema.session.key]["cookie"], "Tue, 07 Jan 2000 01:48:07 UTC", **app.schema.session.cookie["options"])

        raise io.Abort(*app.schema.logout.on_successs_raise)

class Session:
    __slots__ = ()
    def __init__(app):
        ...

    async def validate_session(app, r: io.BlazeioProtocol, cookie: str):
        if app.session_cache and (session := app.session_cache.get(cookie)):
            r.store[app.schema.session.key] = session
            return

        if (session := await app.database("SELECT u.*, s.* FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.cookie = ? AND s.expires_at > ?;", cookie, io.dt.now(io.UTC).isoformat())):
            r.store[app.schema.session.key] = session
            if app.session_cache:
                app.session_cache.add(cookie, session)

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

class SessionCache:
    __slots__ = ("sessions", "max_size")
    def __init__(app, max_size: int = 1000):
        app.sessions, app.max_size = io.ddict(), max_size

    def add(app, cookie: str, session):
        if len(app.sessions) >= app.max_size: return
        app.sessions[cookie] = session

    def get(app, cookie: str):
        if (session := app.sessions.get(cookie)):
            if (io.dt.now() > io.dt.fromisoformat(session.get("expires_at")).replace(tzinfo=None)):
                app.sessions.pop(cookie)
            else:
                return session

class Authenticator(Register, Login, Session):
    __slots__ = ("database", "schema", "hashing_key", "_register", "_login", "_logout", "session_cache")
    routes = io.Routemanager()
    def __init__(app, database, hashing_key: str, register: dict, login: dict, logout: dict, session: dict, session_cache: (SessionCache, None) = None):
        app.database, app.hashing_key = database, hashing_key
        app.session_cache = session_cache
        app.schema = io.ddict(
            register = io.ddict(register),
            login = io.ddict(login),
            logout = io.ddict(logout),
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