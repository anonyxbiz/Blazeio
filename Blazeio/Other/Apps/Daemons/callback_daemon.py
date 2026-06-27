# ./Other/Apps/Daemons/callback_daemon.py
import Blazeio as io

class CbDaemon:
    __slots__ = ("callbacks", "event", "asleep", "task")
    def __init__(app, callbacks, event: (io.SharpEvent, None) = None, asleep: int = 60):
        app.callbacks, app.event, app.asleep, app.task = list(callbacks), event or io.SharpEvent(), asleep, io.create_task(app.daemon())

    async def daemon(app):
        while True:
            await app.event.wait_clear()
            for callback in app.callbacks: callback()

            await io.sleep(app.asleep) # Sleep in between to avoid rapid wakeups

if __name__ == "__main__": ...