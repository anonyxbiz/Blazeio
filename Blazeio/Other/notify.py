# .Blazeio.Other.notify.py
import Blazeio as io

class Notify:
    __slots__ = ("update_event", "notifications", "ended", "max_len", "exit_exception", "exit_tuple", "message_type")
    def __init__(app, max_len: int = 1, message_type: any = None):
        app.update_event, app.ended, app.max_len, app.message_type, app.exit_tuple, app.notifications = io.SharpEvent(), False, max_len, message_type, None, io.deque()

    def __iadd__(app, message: any):
        while len(app.notifications) >= app.max_len:
            app.notifications.popleft()
        if message:
            if app.message_type == dict:
                message = io.ddict(dt = io.dt.now(io.UTC), message = message)
            app.notifications.append(message)
        app.update_event.set()
        return app

    def __await__(app):
        _ = yield from app.update_event.wait_clear().__await__()
        if app.exit_tuple:
            exc_type, exc_value, traceback = app.exit_tuple
            if exc_value: raise exc_value

        return _

    def append(app, message: any):
        return app.__iadd__(message)

    async def __aenter__(app):
        return app

    async def __aexit__(app, exc_type, exc_value, traceback):
        app.exit_tuple = (exc_type, exc_value, traceback)
        app.ended = True
        app.update_event.set()
        return False

    async def __aiter__(app):
        while not app.ended:
            await app.update_event.wait_clear()
            while app.notifications: yield app.notifications.popleft()
        if app.exit_tuple:
            exc_type, exc_value, traceback = app.exit_tuple
            if exc_value: raise exc_value

class _getNotify:
    __slots__ = ()
    def __init__(app):
        ...
    
    def __getattr__(app, key):
        if not (notify := io.Taskscope.get("getNotify")):
            io.Taskscope.getNotify = (notify := Notify())

        return getattr(notify, key)

if __name__ == "__main__": ...