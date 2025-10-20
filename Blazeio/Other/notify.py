# .Blazeio.Other.notify.py
import Blazeio as io

@io.Scope
class Notify:
    __slots__ = ("update_event", "notifications", "ended", "max_len")
    def __init__(app, max_len: int = 10):
        app.update_event, app.ended, app.max_len = io.SharpEvent(), False, max_len
        app.notifications = io.deque()
        io.Taskscope.getNotify = app

    def __iadd__(app, notification: str):
        while len(app.notifications) >= app.max_len:
            app.notifications.popleft()

        app.notifications.append("[%s] -> %s" % (io.timef.now(), str(notification)))
        app.update_event.set()
        return app
    
    def append(app, notification: str):
        return app.__iadd__(notification)

    async def __aenter__(app):
        return app

    async def __aexit__(app, *args):
        app.ended = True
        app.update_event.set()
        return False

    async def __aiter__(app):
        while not app.ended:
            await app.update_event.wait_clear()
            while app.notifications: yield app.notifications.popleft()

class _getNotify:
    __slots__ = ()
    def __init__(app):
        ...
    
    def __getattr__(app, key):
        if not (notify := io.Taskscope.get("getNotify")):
            io.Taskscope.getNotify = (notify := Notify())

        return getattr(notify, key)

io.Scope.getNotify = _getNotify()

if __name__ == "__main__": ...