# ./Other/Apps/Middleware/cors.py
import Blazeio as io

class Cors:
    __slots__ = ("allow_origins", "allow_credentials", "allow_methods", "allow_headers", "expose_headers", "max_age", "vary")
    routes: io.Routemanager = io.Routemanager()
    def __init__(app, allow_origins: tuple, allow_credentials: bool = True, allow_methods: tuple = ("*",), allow_headers: tuple = ("*",), expose_headers: tuple = (), max_age: int = 600, vary: str = "Origin"):
        app.allow_origins, app.allow_credentials, app.allow_methods, app.allow_headers, app.expose_headers, app.max_age, app.vary = allow_origins, allow_credentials, allow_methods, allow_headers, expose_headers, max_age, vary

    def __call__(app, *args, **kwargs):
        return app.routes(*args, **kwargs)

    async def before_middleware(app, r: io.BlazeioProtocol):
        if not (route := app.routes.get(r.path)): return

        if not (origin := r.headers.get("Origin")): return

        if "*" not in app.allow_origins and origin not in app.allow_origins:
            raise io.Abort("Origin not allowed", 403)

        if r.method == "OPTIONS":
            if "*" not in app.allow_methods and (requested_method := r.headers.get("Access-Control-Request-Method")) and requested_method not in app.allow_methods:
                raise io.Abort("Method not allowed", 405)

            if "*" not in app.allow_headers and (requested_headers := r.headers.get("Access-Control-Request-Headers")):
                if any(header not in app.allow_headers for header in [h.strip() for h in requested_headers.split(",") if h.strip()]):
                    raise io.Abort("Headers not allowed", 400)

            cors_headers = (
                b"Access-Control-Allow-Origin: %b\r\n" % (b"*" if "*" in app.allow_origins else origin.encode()),
                b"Access-Control-Allow-Methods: %b\r\n" % (", ".join(app.allow_methods)).encode(),
                b"Access-Control-Allow-Headers: %b\r\n" % (", ".join(app.allow_headers)).encode(),
                b"Access-Control-Max-Age: %d\r\n" % app.max_age,
                b"Access-Control-Allow-Credentials: %b\r\n" % str(app.allow_credentials).encode(),
                b"Vary: %b\r\n" % str(app.vary).encode(),
            )

            if app.expose_headers:
                cors_headers += (b"Access-Control-Expose-Headers: %b\r\n" % (", ".join(app.expose_headers)).encode(),)

            r += cors_headers
            raise io.Abort("", 204)

        else:
            cors_headers = (
                b"Access-Control-Allow-Origin: %b\r\n" % (b"*" if "*" in app.allow_origins else origin.encode()),
                b"Access-Control-Allow-Credentials: %b\r\n" % str(app.allow_credentials).encode(),
            )

            if app.expose_headers:
                cors_headers += (b"Access-Control-Expose-Headers: %b\r\n" % (", ".join(app.expose_headers)).encode(),)

            if app.vary:
                cors_headers += (b"Vary: %b\r\n" % str(app.vary).encode(),)

            r += cors_headers

if __name__ == "__main__":
    # Example usage
    cors = Cors(
        allow_origins = ("http://localhost:3000", "https://example.com"),
        allow_credentials = True,
        allow_methods = ("GET", "POST", "PUT", "DELETE", "OPTIONS"),
        allow_headers = ("Content-Type", "Authorization", "X-Requested-With"),
        expose_headers = ("X-Total-Count", "X-Custom-Header"),
        max_age = 86400,
        vary = "Origin"
    )
    
    # Register a route for CORS
    @cors("/api/data")
    async def handle_data(r: io.BlazeioProtocol):
        # Your route handler here
        return b"Data response"
    
    print("CORS Middleware initialized")