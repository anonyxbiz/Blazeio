# Blazeio.Dependencies.atimeout
from ...Dependencies import *

class ClientTimeout:
    __slots__ = ("timeout", "task", "cb")
    def __init__(app, timeout: int):
        app.timeout = timeout
    
    def abort_protocol(app):
        if (protocol := getattr(app.task, "__BlazeioClientProtocol__", None)):
            protocol.transport.abort()
            protocol.connection_lost(Protocoltimeout())

    async def __aenter__(app):
        app.task = current_task()
        app.cb = ReMonitor.add_callback(app.timeout, app.abort_protocol)
        return app

    async def __aexit__(app, *args):
        ReMonitor.rm_callback(app.cb)
        return False

async def ayield(every = 0):
    while True:
        yield every
        await sleep(every)

if __name__ == "__main__":
    ...