# Blazeio/Versioning/__main__.py
import Blazeio as io

class App:
    version_line = "__version__ = "
    lineno = 10
    def __init__(app, update: (bool, io.Utype) = False, quiet: (bool, io.Utype) = False):
        io.set_from_args(app, locals(), io.Utype)
        io.ioConf.run(app())

    async def exec_cmd(app, cmd: str):
        shell = await io.create_subprocess_shell(cmd, cwd = io.getcwd(), stdout = io.subprocess.PIPE, stderr = io.subprocess.PIPE, shell = True)

        out = ""

        async for i in shell.stdout:
            i = i.decode()
            out += i
            if not app.quiet: await io.log.green(i)

        if shell.stderr:
            async for i in shell.stderr:
                i = i.decode()
                out += i
                if not app.quiet: await io.log.red(i)

        return out

    async def __call__(app):
        if await app.check_for_update() and app.update:
            await io.plog.green("<line_%d>" % app.lineno, "detail: Installing update", "os_name: %s" % io.os_name)

            if io.os_name == "posix":
                for i in ("pip3 install --break-system-packages git+https://github.com/anonyxbiz/Blazeio.git", "pip3 install git+https://github.com/anonyxbiz/Blazeio.git", "pip install git+https://github.com/anonyxbiz/Blazeio.git"):
                    if "Successfully installed Blazeio" in await app.exec_cmd(i): break
            else:
                await app.exec_cmd("pip install git+https://github.com/anonyxbiz/Blazeio.git")

    async def check_for_update(app):
        await io.plog.green("<line_%d>" % app.lineno, "Checking for update...")
        async with io.getSession.get("https://api.github.com/repos/anonyxbiz/Blazeio/contents/Blazeio/Versioning/__init__.py", io.Rvtools.headers) as resp:
            json = await resp.json()
            data = io.b64decode(json.get("content").encode()).decode()

            version = int("".join(data[data.find(app.version_line) + len(app.version_line):][1:-1].split(".")))
            local_version = int("".join(io.__version__.split(".")))
            cond = local_version < version

            if cond:
                detail = "New version is available"
            else:
                detail = "Blazeio is up-to-date"

            await io.plog.b_green("<line_%d>" % app.lineno, detail, "Local version: %s" % local_version, "Current version: %s" % version)

            return cond

if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser()
    io.add_defaults_to_parser(App, parser, io.Utype)
    App(**parser.parse_args().__dict__)
