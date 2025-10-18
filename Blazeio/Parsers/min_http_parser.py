# Blazeio.Parsers.min_http_parser
__all__ = ("MinParser", "MinParserClient", "MinParsers")
from ..Dependencies import *
from ..Dependencies.alts import *

class HTTP:
    __slots__ = ()
    network_config = ddict(
        http = ddict(
            one_point_one = ddict(
                crlf = b"\r\n",
                dcrlf = b"\r\n\r\n",
                protocol = b"HTTP/1.1",
                initial_delimiter = b' ',
                methods = (b"GET", b"HEAD", b"POST", b"PUT", b"DELETE", b"CONNECT", b"OPTIONS", b"TRACE", b"PATCH"),
                headers = ddict(
                    delimiter = b': ',
                )
            )
        )
    )

class MinParser(HTTP):
    __slots__ = ()
    def __init__(app): ...

    def header_make(app, r: BlazeioProtocol, header: bytes):
        if (idx := header.find(app.network_config.http.one_point_one.headers.delimiter)) != -1:
            if (key := header[:idx].decode().capitalize()) in r.headers:
                if not isinstance(r.headers[key], (list,)):
                    r.headers[key] = [r.headers[key]]
                r.headers[key].append(header[idx + len(app.network_config.http.one_point_one.headers.delimiter):].decode())
            else:
                r.headers[key] = header[idx + len(app.network_config.http.one_point_one.headers.delimiter):].decode()

    def header_parser(app, r: BlazeioProtocol, header: bytes):
        r.headers = ddict()
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

class MinParserClient(HTTP):
    __slots__ = ("max_buff_size",)
    def __init__(app, max_buff_size: int = 102400): set_from_args(app, locals(), int)

    def header_make(app, r: BlazeioProtocol, header: bytes):
        if (idx := header.find(app.network_config.http.one_point_one.headers.delimiter)) != -1:
            if (key := header[:idx].decode().lower()) in r.response_headers:
                if not isinstance(r.response_headers[key], (list,)):
                    r.response_headers[key] = [r.response_headers[key]]
                r.response_headers[key].append(header[idx + len(app.network_config.http.one_point_one.headers.delimiter):].decode())
            else:
                r.response_headers[key] = header[idx + len(app.network_config.http.one_point_one.headers.delimiter):].decode()

    def header_parser(app, r: BlazeioProtocol, header: bytes):
        r.response_headers = ddict()
        while header:
            if (idx := header.find(app.network_config.http.one_point_one.crlf)) == -1:
                app.header_make(r, header)
                break
            else:
                _, header = app.header_make(r, header[:idx]), header[idx + len(app.network_config.http.one_point_one.crlf):]

    def set_method(app, r: BlazeioProtocol, header: bytes):
        if (idx := header.find(app.network_config.http.one_point_one.initial_delimiter)) == -1: raise ClientGotInTrouble("Unknown Server Protocol")

        prot, header = header[:idx].decode("utf-8"), header[idx + 1:]

        if (idx := header.find(app.network_config.http.one_point_one.initial_delimiter)) == -1: raise ClientGotInTrouble("Unknown Server Protocol")

        r.status_code, header = int(header[:idx].decode("utf-8")), header[idx + 1:]

        if (idx := header.find(app.network_config.http.one_point_one.initial_delimiter)) == -1: raise ClientGotInTrouble("Unknown Server Protocol")

        r.reason_phrase, header = header[:idx].decode("utf-8"), header[idx + 1:]

        app.header_parser(r, header)

        r.received_len, r.content_length, r.content_type = 0, int(r.response_headers.get('content-length', 0)), r.response_headers.get("content-type", "")

        if r.response_headers.get("transfer-encoding"):
            r.handler = r.handle_chunked
        elif r.response_headers.get("content-length"):
            r.handler = r.handle_raw
        else:
            r.handler = r.protocol.pull

        return r

    def parse(app, r: BlazeioProtocol, buff: bytes):
        idx = buff.find(app.network_config.http.one_point_one.dcrlf)
        header, body = buff[:idx], buff[idx + len(app.network_config.http.one_point_one.dcrlf):]
        app.set_method(r, header)
        return body
    
    async def aparse(app, r: BlazeioProtocol):
        buff = bytearray()
        valid = False

        if not r.protocol or r.protocol.tranport.is_closing(): raise ServerDisconnected()

        while True:
            if (chunk := await r.protocol):
                buff.extend(chunk)

            if not valid:
                if len(buff) < 4: continue
                if app.network_config.http.one_point_one.protocol in buff:
                    valid = True
                else:
                    buff = buff[len(buff)-4:]
                    continue
            
            if app.network_config.http.one_point_one.dcrlf in buff: break

            if len(buff) >= app.max_buff_size:
                raise ClientGotInTrouble("headers exceeded the max_buff_size")

        if app.network_config.http.one_point_one.dcrlf in buff:
            if (body := app.parse(r, buff)):
                r.protocol.prepend(body)

        return r

MinParsers = ddict(server = MinParser(), client = MinParserClient())

if __name__ == "__main__": ...