# Blazeio.Bench.Modules.Server.manager.py
import Blazeio as io

class Manager:
    def __init__(app):
        app.payload = b"." * app.payload_size

    async def handle_all_middleware(app, r: io.BlazeioProtocol, content: bytes = b"."*1024):
        await r.prepare({"Content-Type": r.headers.get("Content-type"), "Content-Length": str((len(content)*app.writes))}, 200)

        for i in range(app.writes):
            await r.writer(content)

if __name__ == "__main__":
    ...