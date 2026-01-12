class BlazeioException(Exception):
    __slots__ = ()

class Err(BlazeioException):
    __slots__ = (
        'message',
    )
    def __init__(app, message=None):
        app.message = message

    def __str__(app) -> str:
        return str(app.message)

class ClientDisconnected(BlazeioException):
    __slots__ = ('message', 'origin')
    def __init__(app, message: (None, str) = None, origin: (None, str) = None):
        app.message, app.origin = message or "Client has disconnected.", origin

    def __str__(app) -> str:
        return str(app.message)

class ServerDisconnected(BlazeioException):
    __slots__ = ('message', 'origin')
    def __init__(app, message: (None, str) = None, origin: (None, str) = None):
        app.message, app.origin = message or "Server has disconnected.", origin

    def __str__(app) -> str:
        return str(app.message)

class ServerGotInTrouble(BlazeioException):
    __slots__ = ('message')
    def __init__(app, message=None):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class ClientGotInTrouble(BlazeioException):
    __slots__ = ('message')
    def __init__(app, message=None):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class Protocoltimeout(BlazeioException):
    __slots__ = ('message')
    def __init__(app, message="Protocol timed out..."):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class Missingdependency(BlazeioException):
    __slots__ = ('message')
    def __init__(app, message="Module not imported..."):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class CloseConnection(BlazeioException):
    __slots__ = ()
    def __init__(app): ...

class ProtocolError(BlazeioException):
    __slots__ = ('message',)
    def __init__(app, message=None):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class Eof(BlazeioException):
    __slots__ = ()
    def __init__(app, *args): ...

class ModuleError(BlazeioException):
    __slots__ = ('name', 'error', 'message')
    def __init__(app, name: str, *error):
        app.name, app.error, app.message = name, error, None

    def get_message(app) -> str:
        if app.message: return app.message
        app.message, indent = "[%s] Error:" % app.name, 0
        for i in app.error:
            indent += 1
            app.message += "\n%s%s" % (" " * indent, i)

        return app.message

    def __str__(app) -> str:
        return app.get_message()

if __name__ == "__main__": ...