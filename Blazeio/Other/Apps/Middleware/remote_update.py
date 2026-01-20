# ./Other/Apps/Middleware/remote_update.py
import Blazeio as io

class Updater:
    __slots__ = ("web", "auth_token", "route", "auth_token_key", "cmd")
    def __init__(app, auth_token: str, route: str = "/system/remote/update", auth_token_key: str = "auth_token", cmd: str = " ".join(["git", "stash", "&&", "git", "pull"])):
        io.set_from_args(app, locals(), (str,))

    def __server_instance__(app, web: io.App):
        app.web = web
        app.web.add_route(app.handle, app.handle, app.route)

class Git(Updater):
    async def handle(app, r: io.BlazeioProtocol):
        if not (auth_token := r.params().get(app.auth_token_key) or r.headers.get(app.auth_token_key)):
            raise io.Abort("auth_token is required", 403)

        elif auth_token != app.auth_token:
            raise io.Abort("invalid token", 403)
        
        async with io.ConnectionTaskShield(r):
            await io.Deliver.text("Ok")

            if "Already up to date." in (await io.getLoop.run_in_executor(None, lambda: io.sb_run(app.cmd, shell = True, stdout = io.PIPE, stderr = io.PIPE, text = True))).stdout: return

            await app.web.exit(terminate = True)

if __name__ == "__main__": ...