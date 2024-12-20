from ..Dependencies import p, dumps, loads, Err, Log, sleep

class Stream:
    @classmethod
    async def init(app, r, *args, **kwargs):
        await r.prepare(*args, **kwargs)
        
        r.prepared = True

    @classmethod
    async def write(app, r, data: bytes):
        await r.write(data)

    @classmethod
    async def prepared(app, r):
        if "prepared" in r.__dict__: return True
            
class Deliver:
    @classmethod
    async def json(app, r, data, _dump=True, _encode=True, status=206, headers={}, reason="Partial Content", indent=4):
        headers_ = dict(headers)
        
        headers_["Content-Type"] = "application/json"
        await r.prepare(headers_, status=status, reason=reason)

        if isinstance(data, (dict,)):
            data = dumps(data, indent=indent)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await r.write(data)

    @classmethod
    async def text(app, r, data, status=206, headers={}, reason="Partial Content"):
        headers = dict(headers)

        headers["Content-Type"] = "text/plain"
        await r.prepare(headers, status=status, reason=reason)

        if not isinstance(data, (bytes, bytearray)):
            data = data.encode()

        await r.write(data)

    @classmethod
    async def redirect(app, r, path, status=302, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status)

    @classmethod
    async def HTTP_301(app, r, path, status=301, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_302(app, r, path, status=302, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_307(app, r, path, status=307, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

    @classmethod
    async def HTTP_308(app, r, path, status=308, headers={}, reason="Redirect"):
        headers["Location"] = path
        await r.prepare(headers, status=status, reason=reason)

class Abort(Exception):
    headers = {}
    __status_meaning__ = {
        400: {
            "title": "Bad Request Status Code",
            "reason": "Bad Request",
            "description": "The request could not be understood or was missing required parameters.",
            "detail": "You made a bad request! Maybe try again with more clarity? The server couldn't quite get what you were asking for."
        },
        401: {
            "title": "Unauthorized Status Code",
            "reason": "Unauthorized",
            "description": "Authentication failed or user does not have permissions for the desired action.",
            "detail": "You shall not pass! Please check your credentials, as you're not authorized to do this action."
        },
        403: {
            "title": "Forbidden Status Code",
            "reason": "Forbidden",
            "description": "The server understands the request, but refuses to authorize it.",
            "detail": "Forbidden! You don't have permission to access this resource. Maybe it’s an exclusive club you’re not invited to?"
        },
        404: {
            "title": "Not Found Status Code",
            "reason": "Not Found",
            "description": "The resource you are looking for could not be found.",
            "detail": "Oops! The resource you're looking for is nowhere to be found. It’s like searching for a unicorn in a haystack!"
        },
        405: {
            "title": "Method Not Allowed Status Code",
            "reason": "Method Not Allowed",
            "description": "The method specified in the request is not allowed for the resource identified by the URL.",
            "detail": "You tried to do something that isn’t allowed here. Perhaps it’s like trying to use a hammer to screw in a nail?"
        },
        406: {
            "title": "Not Acceptable Status Code",
            "reason": "Not Acceptable",
            "description": "The server can only generate a response that is not acceptable according to the Accept headers sent in the request.",
            "detail": "Your request isn’t acceptable. Maybe the server just doesn’t like your taste? It’s trying to find something you’d like though!"
        },
        407: {
            "title": "Proxy Authentication Required Status Code",
            "reason": "Proxy Authentication Required",
            "description": "The request requires authentication through a proxy.",
            "detail": "Your request is stuck behind a proxy gate. It needs to prove it's worthy before it gets through. Check your proxy credentials!"
        },
        408: {
            "title": "Request Timeout Status Code",
            "reason": "Request Timeout",
            "description": "The server timed out waiting for the request.",
            "detail": "The server got too tired of waiting for you! It’s been too long and it needs a break. Try again later, will ya?"
        },
        409: {
            "title": "Conflict Status Code",
            "reason": "Conflict",
            "description": "The request could not be completed due to a conflict with the current state of the resource.",
            "detail": "There’s a conflict! It’s like two people fighting for the last cookie. Try again when everyone calms down!"
        },
        410: {
            "title": "Gone Status Code",
            "reason": "Gone",
            "description": "The resource requested is no longer available and will not be available again.",
            "detail": "Well, the resource is gone, like your favorite TV show that got canceled. It’s not coming back, sorry!"
        },
        411: {
            "title": "Length Required Status Code",
            "reason": "Length Required",
            "description": "The server refuses to accept the request without a defined Content-Length header.",
            "detail": "Your request didn’t bring enough information. It's like going to a party without a gift – they want the full package!"
        },
        412: {
            "title": "Precondition Failed Status Code",
            "reason": "Precondition Failed",
            "description": "The server does not meet one of the preconditions that the requester put on the request.",
            "detail": "You asked for something that wasn’t quite ready yet. It’s like trying to eat the cake before it’s baked!"
        },
        413: {
            "title": "Payload Too Large Status Code",
            "reason": "Payload Too Large",
            "description": "The request entity is larger than limits defined by the server.",
            "detail": "Your payload is just too big to handle! It’s like trying to fit a giant elephant into a tiny car."
        },
        414: {
            "title": "URI Too Long Status Code",
            "reason": "URI Too Long",
            "description": "The URI provided was too long for the server to process.",
            "detail": "Your URL is so long it could be a novel! Try shortening it or find a more concise path."
        },
        415: {
            "title": "Unsupported Media Type Status Code",
            "reason": "Unsupported Media Type",
            "description": "The request’s media type is not supported by the server.",
            "detail": "The server can’t handle the media type you sent. It’s like trying to play a vinyl on a cassette player – just doesn’t work!"
        },
        416: {
            "title": "Range Not Satisfiable Status Code",
            "reason": "Range Not Satisfiable",
            "description": "The client has asked for a portion of the file, but the server cannot supply that portion.",
            "detail": "Your range request doesn’t match the file. It’s like asking for the last slice of pizza that doesn’t exist!"
        },
        417: {
            "title": "Expectation Failed Status Code",
            "reason": "Expectation Failed",
            "description": "The server cannot meet the requirements of the Expect request-header field.",
            "detail": "Expectations dashed! The server couldn’t meet your request, like asking for a miracle without the magic!"
        },
        418: {
            "title": "I'm a Teapot Status Code",
            "reason": "I'm a Teapot",
            "description": "The teapot is short and stout, but it can't brew coffee.",
            "detail": "I’m a teapot! I can’t brew coffee, no matter how much you ask. This is the famous April Fool's joke status code."
        },
        429: {
            "title": "Too Many Requests Status Code",
            "reason": "Too Many Requests",
            "description": "The user has sent too many requests in a given amount of time.",
            "detail": "You’ve made too many requests! The server needs a break, give it a minute before you try again."
        },
        500: {
            "title": "Internal Server Error Status Code",
            "reason": "Internal Server Error",
            "description": "The server encountered an unexpected condition which prevented it from fulfilling the request.",
            "detail": "Oops! Something went wrong on our end. It’s like the server tripped over its own shoelaces."
        },
        502: {
            "title": "Bad Gateway Status Code",
            "reason": "Bad Gateway",
            "description": "The server received an invalid response from the upstream server it accessed in attempting to fulfill the request.",
            "detail": "Bad gateway! It’s like sending a letter to the wrong address and getting a random response back."
        },
        503: {
            "title": "Service Unavailable Status Code",
            "reason": "Service Unavailable",
            "description": "The server is currently unable to handle the request due to temporary overloading or maintenance of the server.",
            "detail": "The server is taking a break. It’s overloaded or under maintenance, but it’ll be back soon!"
        },
        504: {
            "title": "Gateway Timeout Status Code",
            "reason": "Gateway Timeout",
            "description": "The server did not receive a timely response from the upstream server or some other auxiliary server it needed to access in order to complete the request.",
            "detail": "Timeout! The server waited and waited, but no response came in time. It’s like waiting for a reply to your text, but the other person falls asleep!"
        },
    }

    def __init__(app, message: str = "Forbidden", status: int = 403, headers: dict = {}, **kwargs):
        app.message = str(message)
        app.kwargs = kwargs
        app.status = status
        if headers: app.headers.update(headers)
        
        super().__init__(message)

    def __str__(app) -> str:
        return app.message

    async def respond(app, r):
        if not (status := app.__status_meaning__.get(app.status)):
            await r.prepare(app.headers, app.status, app.kwargs.get("reason", "Something went wrong"))
            return
        
        app.headers["Content-Type"] = "text/html"
        
        await r.prepare(app.headers, app.status, status["reason"])
        
        html = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{status['title']} | Blaze I/O</title>

            <meta name="description" content="{status['description']}">
            <meta name="keywords" content="Blaze I/O">
            <meta name="robots" content="index, follow">
        </head>

        <body>
        
            <main>
                <header>
                    <h1>
                        Blaze I/O
                    </h1>
                </header>
            </main>
            <section>
                <h4>
                    {status['detail']}
                </h4>
            </section>
            
        </body>
        </html>"""

        await r.write(bytearray(html, "utf-8"))

if __name__ == "__main__":
    pass
