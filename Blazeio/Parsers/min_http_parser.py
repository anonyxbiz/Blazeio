# Blazeio.Parsers.min_http_parser
__all__ = ("MinParser",)
from ..Dependencies import *
from ..Dependencies.alts import *

class MinParser:
    __slots__ = ()
    network_config = ddict(
        http = ddict(
            one_point_one = ddict(
                crlf = b"\r\n",
                dcrlf = b"\r\n\r\n",
                start = b"HTTP/1.1",
                initial_delimiter = b' ',
                methods = (b"GET", b"HEAD", b"POST", b"PUT", b"DELETE", b"CONNECT", b"OPTIONS", b"TRACE", b"PATCH"),
                headers = ddict(
                    delimiter = b': ',
                )
            )
        )
    )

    def __init__(app): ...

    def header_make(app, r: BlazeioProtocol, header: bytes):
        if (idx := header.find(app.network_config.http.one_point_one.headers.delimiter)) != -1:
            r.headers[header[:idx].decode().capitalize()] = header[idx + len(app.network_config.http.one_point_one.headers.delimiter):].decode()

    def header_parser(app, r: BlazeioProtocol, header: bytes):
        r.headers = {}
        while header:
            if (idx := header.find(app.network_config.http.one_point_one.crlf)) == -1:
                app.header_make(r, header)
                break
            else:
                _, header = app.header_make(r, header[:idx]), header[idx + len(app.network_config.http.one_point_one.crlf):]

    def set_method(app, r: BlazeioProtocol, header: bytes):
        if (idx := header.find(app.network_config.http.one_point_one.initial_delimiter)) == -1:
            raise Abort("Request has no headers", 400)

        r.method, header = header[:idx].decode("utf-8"), header[idx + 1:]

        if (idx := header.find(app.network_config.http.one_point_one.initial_delimiter)) == -1:
            raise Abort("Request has no method", 400)

        tail, header = header[:idx].decode("utf-8"), header[idx + 1:]
        r.tail, r.path = tail, tail

        if (idx := r.path.find('?')) != -1:
            r.path = r.path[:idx]

        app.header_parser(r, header)

        if r.headers:
            if not r.pull:
                if (content_length := r.headers.get("Content-length")):
                    r.content_length = int(content_length)
                    r.pull = r.handle_raw
                elif (transfer_encoding := r.headers.get("Transfer-encoding")):
                    r.transfer_encoding = transfer_encoding
                    r.pull = r.handle_chunked
                else:
                    r.content_length = 0
                    r.pull = r.handle_raw

        return r

    def parse(app, r: BlazeioProtocol, buff: bytes):
        idx = buff.find(app.network_config.http.one_point_one.dcrlf)
        header, body = buff[:idx], buff[idx + len(app.network_config.http.one_point_one.dcrlf):]
        app.set_method(r, header)
        return body

if __name__ == "__main__": ...