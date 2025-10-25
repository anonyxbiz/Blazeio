# Blazeio.Create.__main__.py
import Blazeio as io
import Blazeio.Other.class_parser as class_parser
from os import mkdir, chdir
from shutil import rmtree

class App:
    __slots__ = ("name", "port", "y", "path", "lineno")
    max_path_loggable_len = 30
    app_files = {
        "/page": {
            "index.html": '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title><!--title--> | <!--app_title--></title>\n    <meta name="description" content="<!--description-->">\n    <meta name="keywords" content="App">\n    <meta name="robots" content="index, follow">\n    <link rel="stylesheet" href="/css/index.css">\n    <link rel="icon" type="image/png" href="/img/logo.png">\n</head>\n<body>\n    <script defer type="module" src="/js/index.js"></script>\n</body>\n</html>'
        },
        "/js": {
            "index.js": 'class Index {\n    constructor() {\n        this.main = document.querySelector("main");\n    }\n\n    async init() {\n        try {\n            document.addEventListener("DOMContentLoaded", this.onLoad.bind(this));\n        } catch (e) {\n            alert(e);\n        }\n    }\n\n    async onLoad() {\n        //\n    };\n\n}\n\nconst index = new Index();\nwindow.index = index;\nindex.init();\n'
        },
        "/css": {
            "index.css": '* {/n    font-family: Arial, sans-serif;/n    --base_text_color: #AEABAF;/n    --border_color: #282828;/n    --base_bg: #121212;/n    --accent-color: #ff4d4f;/n    margin: 0;/n    box-sizing: border-box;/n    --span-font-size: 0.85em;/n    background: transparent;/n}/n/nh1, h2, h3, h4, h5, p, span, textarea, a, input {/n    overflow-wrap: break-word;/n    word-wrap: break-word;/n    word-break: break-all;/n    text-align: center;/n    text-align: start;/n    color: var(--base_text_color);/n    outline: none;/n}/n/np {/n    font-size: 0.90rem;/n}/n/nspan {/n    font-size: var(--span-font-size);/n}/n/nsvg {/n    color: var(--accent-color);/n}/n/nbody {/n    display: flex;/n    flex-direction: column;/n    flex-wrap: wrap;/n    color: var(--base_text_color);/n    padding: 0rem 1rem;/n    width: 100%;/n    height: 100%;/n    --s: 37px;/n    --c: #0000, #282828 0.5deg 119.5deg, #0000 120deg;/n    --g1: conic-gradient(from 60deg at 56.25% calc(425% / 6), var(--c));/n    --g2: conic-gradient(from 180deg at 43.75% calc(425% / 6), var(--c));/n    --g3: conic-gradient(from -60deg at 50% calc(175% / 12), var(--c));/n    background: var(--g1), var(--g1) var(--s) calc(1.73 * var(--s)), var(--g2),/n    var(--g2) var(--s) calc(1.73 * var(--s)), var(--g3) var(--s) 0,/n    var(--g3) 0 calc(1.73 * var(--s)) #1e1e1e;/n    background-size: calc(2 * var(--s)) calc(3.46 * var(--s));/n}/n/nheader {/n    display: flex;/n    flex-direction: row;/n    background: transparent;/n    width: 95%;/n    position: fixed;/n    top: 0;/n    z-index: 2000;/n    place-content: center;/n    place-items: center;/n    padding-top: 1rem;/n    gap: 1rem;/n    padding-bottom: 1.5rem;/n}/n/nfooter {/n    display: flex;/n    flex-direction: column;/n    justify-content: center;/n    z-index: 1000;/n    background: transparent;/n    width: 100%;/n    position: fixed;/n    bottom: 0;/n    z-index: 2000;/n    place-content: center;/n    place-items: center;/n    gap: 10px;/n    padding-top: 0.2rem;/n    padding-bottom: 0.5rem;/n}/n/nheader img, footer img {/n    max-width: 50px;/n    max-height: 50px;/n    border-radius: 20px;/n    margin-right: 10px;/n}/n/nh1 {/n    font-size: 0.9em;/n    color: var(--base_text_color);/n}/n/nimg {/n    width: 100%;/n    height: 100%;/n    max-width: 300px;/n    max-height: 200px;/n    object-fit: cover;/n    border-radius: 20px;/n}/n/na {/n    text-decoration: none;/n}/n/nspan {/n    display: flex;/n    flex-direction: column;/n    place-items: center;/n    place-content: center;/n    border-radius: 20px;/n    color: var(--base_text_color);/n    position: relative;/n    outline: none;/n    background-color: #282828;/n    text-align: start;/n    padding: 0.1rem 0.5rem;/n}/n'.replace('/n', '\n')
        },
        "/img": {},
        "../requirements.txt": "git+https://github.com/anonyxbiz/Blazeio.git\nuvloop",
        "../__init__.py": ""
    }

    def __init__(app, name: (str, io.Utype, class_parser.Positional) = None, port: (int, io.Utype) = 7000, y: (str, io.Utype, class_parser.Store) = None):
        io.set_from_args(app, locals(), io.Utype)
        app.path = io.path.join(io.getcwd(), app.name)
        app.lineno = 5
        io.ioConf.run(app.run())

    def get_lineno(app, logger):
        # If the logger is bright `startswith("b_")` it indicates a response log to a previous log, so we log it on the previous line, replacing the previous line.

        app.lineno += 3
        if logger.__name__.startswith("b_"):
            app.lineno -= 3

        return app.lineno
    
    def set_app_file(app):
        app.app_files["../app.py"] = ('import Blazeio as io\nfrom Blazeio.Other.proxy import add_to_proxy, available\n\nweb = io.App("0.0.0.0", %d, name = "%s")\n\nweb.attach(io.StaticServer(root = "/", root_dir = io.path.join(io.getcwd(), "static"), chunk_size = 1024*100, page_dir = "page", home_page = "index.html"))\n\n@web.attach\nclass App:\n    static_path = "static"\n    def __init__(app):\n        ...\n\n    async def _app_monitoring_sessionpool(app, r: io.BlazeioProtocol):/n        pool = io.getSession.pool()/n        await r.prepare({"Content-type": io.Ctypes.json, "Transfer-encoding": "chunked"}, 200)/n        /n        await r.write(b\'{"sessions": \')/n        await r.write(str(len(pool.sessions)).encode())/n        await r.write(b\', "connections": \')/n        await r.write(str(sum([len(session) for session in pool.sessions.values()])).encode())/n        await r.write(b\', "waiters": \')/n        await r.write(str(sum([sum([i.context.waiter_count for i in session]) for session in pool.sessions.values()])).encode())/n        await r.write(b\'}\')\n\nif __name__ == "__main__":\n    if available():\n       if io.debug_mode: add_to_proxy("%s.localhost", web.ServerConfig.port, "%s.certificate.pem", "%s.keyfile.pem", enforce_https = True)\n       else: add_to_proxy("%s.com", web.ServerConfig.port, from_certbot = True, enforce_https = True)\n    web.with_keepalive()\n    with web:\n        web.runner()'.replace('/n', '\n')) % (app.port, app.name, app.name, app.name, app.name, app.name)

    async def create(app):
        await io.plog.cyan("Creating a Blazeio web application named: (%s), which will run on port: (%d), application directory: (%s)..." % (app.name, app.port, app.path[-app.max_path_loggable_len:]))
        
        app.set_app_file()

        if io.path.exists(app.path):
            if not app.y:
                raise io.Eof(await io.plog.b_red("%s Exists, project creation aborted" % app.path[-app.max_path_loggable_len:]))
            else:
                await io.plog.yellow("Dir: (%s) Exists, Removing it..." % app.path[-app.max_path_loggable_len:])
                await io.to_thread(rmtree, app.path)
                await io.plog.b_yellow("Removed dir: (%s)..." % app.path[-app.max_path_loggable_len:])
        
        await io.plog.yellow("Creating dir: (%s)..." % app.path[-app.max_path_loggable_len:])

        await io.to_thread(mkdir, app.path)
        
        await io.plog.b_yellow("Created dir: (%s)..." % app.path[-app.max_path_loggable_len:])

        await io.plog.yellow("Changing to dir: (%s)..." % app.path[-app.max_path_loggable_len:])

        await io.to_thread(chdir, app.path)

        await io.plog.b_yellow("Changed to dir: (%s)..." % app.path[-app.max_path_loggable_len:])
        
        static_dir = io.path.join(io.getcwd(), "static")

        await io.plog.yellow("Creating dir: (%s)..." % static_dir[-app.max_path_loggable_len:])

        await io.to_thread(mkdir, static_dir)
        
        await io.plog.b_yellow("Created dir: (%s)..." % static_dir[-app.max_path_loggable_len:])

        await io.plog.yellow("Changing to dir: %s..." % static_dir[-app.max_path_loggable_len:])

        await io.to_thread(chdir, static_dir)
        
        await io.plog.b_yellow("Changed to dir: (%s)..." % static_dir[-app.max_path_loggable_len:])
        
        for k, v in app.app_files.items():
            if k.startswith("/"):
                k = k[1:]
            else:
                file = io.path.join(io.getcwd(), k)
                await io.plog.cyan("Creating file: (%s)..." % file[-app.max_path_loggable_len:])
                await io.asave(file, v.encode())
                await io.plog.b_cyan("Created file: (%s?..." % file[-app.max_path_loggable_len:])
                continue

            static_dir = io.path.join(io.getcwd(), k)
            
            await io.plog.yellow("Creating dir: (%s)..." % static_dir[-app.max_path_loggable_len:])

            await io.to_thread(mkdir, static_dir)
            
            await io.plog.b_yellow("Created dir: (%s)..." % static_dir[-app.max_path_loggable_len:])

            await io.plog.yellow("Changing to dir: (%s)..." % static_dir[-app.max_path_loggable_len:])

            await io.to_thread(chdir, static_dir)
            
            await io.plog.b_yellow("Changed to dir: (%s)..." % static_dir[-app.max_path_loggable_len:])

            if v:
                for k2, v2 in v.items():
                    file = io.path.join(io.getcwd(), k2)
                    await io.plog.cyan("Creating file: (%s)" % file[-app.max_path_loggable_len:])

                    await io.asave(file, v2.encode())

                    await io.plog.b_cyan("Created file: (%s)" % file[-app.max_path_loggable_len:])
            
            prev_dir = io.path.join(io.getcwd(), "..")
            
            await io.plog.yellow("Changing to dir: (%s)..." % prev_dir[-app.max_path_loggable_len:])

            await io.to_thread(chdir, prev_dir)
            
            await io.plog.b_yellow("Changed to dir: (%s)..." % prev_dir[-app.max_path_loggable_len:])

        await io.plog.cyan("Creating a Blazeio web application named: (%s), which will run on port: (%d), application directory: (%s)..." % (app.name, app.port, app.path[-app.max_path_loggable_len:]))
    
    async def run(app):
        async with io.Ehandler(ignore = io.Eof):
            io.Taskscope.plog_lineno_callback = app.get_lineno # Add a dynamic callback to the current task's Blazeio.Taskscope, so that Blazeio.plog can call it to provide the console line to log logs, Blazeio.plog detects if `plog_lineno_callback` callback is set in the current task's scope and if so it uses to get the lineno else it logs normally without line formatting.
            await app.create()

if __name__ == "__main__":
    App(**class_parser.Parser(App, io.Utype).args())