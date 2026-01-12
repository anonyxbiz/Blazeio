# ./Other/Apps/Middleware/path_access.py
import Blazeio as io

class PathAccess:
    __slots__ = ("root", "auth", "on_fail_raise")
    prerequisites: dict = io.ddict(
        session = ("key",),
        access = ("key", "value"),
    )
    def __init__(app, root: str, auth: dict, on_fail_raise: tuple):
        io.set_from_args(app, locals(), (str, dict, tuple))
        app.validator()
    
    def validator(app):
        if not app.root:
            raise io.ModuleError("PathAccess", "validator", "validation failed", "root is required")
        
        for key, value in app.prerequisites.items():
            if not (prerequisite := app.auth.get(key)):
                raise io.ModuleError("PathAccess", "validator", "validation failed", "auth.%s is required" % key)

            for i in value:
                if not prerequisite.get(i):
                    raise io.ModuleError("PathAccess", "validator", "validation failed", "auth.%s.%s is required" % (key, i))

    async def before_middleware(app, r: io.BlazeioProtocol):
        if not r.path.startswith(app.root): return

        if not r.store:
            raise io.ModuleError("PathAccess", "Middleware", "r.store must be set")

        if not (session := r.store.get(app.auth["session"]["key"])):
            raise io.ModuleError("PathAccess", "Middleware", "session not found")

        if not (access := session.get(app.auth["access"]["key"])):
            raise io.ModuleError("PathAccess", "Middleware", "access not found")

        if access != app.auth["access"]["value"]:
            raise io.Abort(*app.on_fail_raise)

if __name__ == "__main__": ...