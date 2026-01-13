# ./Other/Apps/Auth/authentication.py
import Blazeio as io
from hmac import new as hmac_new
from hashlib import sha1 as sha256

class PasswordHasher:
    __slots__ = ()
    def __init__(app):
        ...
    
    def password_hasher(app, password: bytes):
        return io.urlsafe_b64encode(hmac_new(app.hashing_key.encode(), password, sha256).digest()).decode()

class Register:
    __slots__ = ()
    def __init__(app):
        @app.add_route
        def _register(r: io.BlazeioProtocol, route: str = app.schema.register.endpoint):
            return app.register(r)

    async def register(app, r: io.BlazeioProtocol):
        data = await r.body_or_params()

        if not (email := data.get(app.email_key)):
            raise io.Abort("%s is required" % app.email_key, 403)

        if not (username := data.get(app.username_key)):
            raise io.Abort("%s is required" % app.username_key, 403)

        if not (password := data.get(app.password_key)):
            raise io.Abort("%s is required" % app.password_key, 403)

        if await app.database("SELECT %s FROM %s WHERE %s = ?;" % (app.email_key, app.users_column, app.email_key), email):
            raise io.Abort("%s already registered." % app.email_key, 403)

        if await app.database("SELECT %s FROM %s WHERE %s = ?;" % (app.username_key, app.users_column, app.username_key), username):
            raise io.Abort("%s is taken" % app.username_key, 403)

        await app.database(
            "INSERT INTO %s (%s, %s, %s, %s) VALUES (?, ?, ?, ?);" % (app.users_column, app.email_key, app.username_key, app.password_key, app.ip_key),
            email,
            username,
            app.password_hasher(password.encode()),
            r.ip_host
        )

        if not await app.database("SELECT %s FROM %s WHERE %s = ?;" % (app.username_key, app.users_column, app.username_key), username):
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
        if not (username := data.get(app.username_key)) or not (password := data.get(app.password_key)):
            raise io.Abort("%s and %s are required" % (app.username_key, app.password_key), 403)

        if not (user := await app.database("SELECT %s FROM %s WHERE %s = ? AND %s = ?;" % (app.user_id_key, app.users_column, app.username_key, app.password_key), username, app.password_hasher(password.encode()))):
            raise io.Abort("Invalid credentials", 403)

        await app.database(
            "INSERT INTO %s (%s, %s, %s, %s) VALUES (?, ?, ?, ?);" % (app.sessions_column, app.user_id_key, app.cookie_key, app.expires_at_key, app.ip_key),
            user.get(app.user_id_key),
            cookie := await app.database.unique_id("SELECT %s FROM %s WHERE %s = ? AND %s = ?" % (app.cookie_key, app.sessions_column, app.user_id_key, app.cookie_key), user.get(app.user_id_key), start = 32),
            (expires := (io.dt.now(io.UTC) + io.timedelta(**app.schema.session.expires_after))).isoformat(),
            r.ip_host,
        )

        if not await app.database("SELECT %s FROM %s WHERE %s = ?;" % (app.cookie_key, app.sessions_column, app.cookie_key), cookie):
            raise io.Abort("Something went wrong", 500)

        r.set_cookie(app.schema.session.cookie["name"], cookie, expires.strftime("%a, %d %b %Y %H:%M:%S UTC"), **app.schema.session.cookie["options"])

        raise io.Abort(*app.schema.login.on_successs_raise)

    async def logout(app, r: io.BlazeioProtocol):
        await app.database("DELETE FROM %s WHERE %s = ? AND %s = ?;" % (app.sessions_column, app.session_id_key, app.cookie_key), r.store[app.schema.session.key][app.session_id_key], r.store[app.schema.session.key][app.cookie_key])

        r.set_cookie(app.schema.session.cookie["name"], r.store[app.schema.session.key][app.cookie_key], "Tue, 07 Jan 2000 01:48:07 UTC", **app.schema.session.cookie["options"])

        raise io.Abort(*app.schema.logout.on_successs_raise)

class Session:
    __slots__ = ()
    def __init__(app):
        ...

    async def validate_session(app, r: io.BlazeioProtocol, cookie: str):
        if app.session_cache and (session := app.session_cache.get(cookie)):
            r.store[app.schema.session.key] = session
            return

        if (session := await app.database("SELECT u.*, s.* FROM %s s JOIN %s u ON u.%s = u.%s WHERE s.%s = ? AND s.%s > ?;" % (app.sessions_column, app.users_column, app.user_id_key, app.user_id_key, app.cookie_key, app.expires_at_key), cookie, io.dt.now(io.UTC).isoformat())):
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
        if not r.path in app.routes and not r.path.startswith(app.wildcard_paths): return

        await app.auth_user(r)

        if not r.store.session:
            raise io.Abort(*app.schema.session.on_fail_raise)

class SessionCache:
    __slots__ = ("sessions", "max_size", "expires_at_key")
    def __init__(app, max_size: int = 1000, expires_at_key: str = "expires_at"):
        app.sessions, app.max_size, app.expires_at_key = io.ddict(), max_size, expires_at_key

    def add(app, cookie: str, session):
        if len(app.sessions) >= app.max_size: return
        app.sessions[cookie] = session

    def get(app, cookie: str):
        if (session := app.sessions.get(cookie)):
            if (expires_at := session.get(app.expires_at_key)) and (io.dt.now() > io.dt.fromisoformat(expires_at).replace(tzinfo=None)):
                app.sessions.pop(cookie)
            else:
                return session

class Authenticator(PasswordHasher, Register, Login, Session):
    __slots__ = ("database", "schema", "hashing_key", "_register", "_login", "_logout", "session_cache", "wildcard_paths", "users_column", "user_id_key", "email_key", "username_key", "password_key", "sessions_column", "session_id_key", "cookie_key", "expires_at_key", "ip_key")
    routes = io.Routemanager()
    def __init__(app, database, hashing_key: str, register: dict, login: dict, logout: dict, session: dict, session_cache: (SessionCache, None) = None, wildcard_paths: tuple = (), users_column: str = "users", user_id_key: str = "user_id", email_key: str = "email", username_key: str = "username", password_key: str = "password", sessions_column: str = "sessions", session_id_key: str = "session_id", cookie_key: str = "cookie", expires_at_key: str = "expires_at", ip_key: str = "ip"):
        app.database, app.hashing_key = database, hashing_key
        app.session_cache = session_cache
        app.wildcard_paths, app.users_column, app.user_id_key, app.email_key, app.username_key, app.password_key, app.sessions_column, app.session_id_key, app.cookie_key, app.expires_at_key, app.ip_key = wildcard_paths, users_column, user_id_key, email_key, username_key, password_key, sessions_column, session_id_key, cookie_key, expires_at_key, ip_key
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