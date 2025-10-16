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
    __slots__ = ('message')
    def __init__(app, message: (None, str) = "Client has disconnected."):
        app.message = message

    def __str__(app) -> str:
        return str(app.message)

class ServerDisconnected(BlazeioException):
    __slots__ = ('message')
    def __init__(app, message: (None, str) = "Server has disconnected."):
        app.message = message

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
    __slots__ = ('message')
    def __init__(app, message=None):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class Eof(BlazeioException):
    __slots__ = ()
    def __init__(app, *args): ...

if __name__ == "__main__": ...