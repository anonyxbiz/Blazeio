# ./Other/Apps/Daemons/callback_daemon.py
import Blazeio as io

class CbDaemon:
    __slots__ = ("callbacks", "event", "task")
    def __init__(app, callbacks, event: (io.SharpEvent, None) = None):
        app.callbacks, app.event, app.task = list(callbacks), event or io.SharpEvent(), io.create_task(app.daemon())

    async def daemon(app):
        while True:
            await app.event.wait_clear()
            for callback in app.callbacks:
                callback()

if __name__ == "__main__": ...