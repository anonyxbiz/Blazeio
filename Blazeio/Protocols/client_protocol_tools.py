from ..Dependencies.alts import *
from ..Modules.request import *
from ..Modules.streaming import ClientContext
from ..Parsers.min_http_parser import *

ssl_context = create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = CERT_NONE

class __Rvtools__:
    __slots__ = ()
    _headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Not A(Brand";v="8", "Chromium";v="115"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 11; U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36'
    }

    def __init__(app): ...

    def dh(app, url: str):
        return {'accept': '*/*', 'accept-language': 'en-US,en;q=0.9', 'origin': url, 'priority': 'u=1, i', 'referer': url, 'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"%s"' % os_name, 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', 'user-agent': 'BlazeI/O', 'connection': 'keep-alive'}

    def __getattr__(app, key, *args):
        key = "_%s" % key
        if not hasattr(app, key): raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, key))

        item = getattr(app, key, *args)

        if isinstance(item, (dict, list)):
            item = ddict(item)

        return item

Rvtools = __Rvtools__()

class Decoders:
    __slots__ = ()
    def __init__(app): ...

    async def _br_decoder(app):
        if not app.decompressor: app.decompressor = Decompressor()

        buff = memarray()

        async for chunk in app.handler():
            buff.extend(chunk)

            if len(buff) >= 1024:
                if len(buff) >= 10240:
                    chunk = await to_thread(app.decompressor.decompress, bytes(buff))
                else:
                    chunk = app.decompressor.decompress(bytes(buff))

                yield chunk
                buff = memarray(buff[len(buff):])

        if buff: yield app.decompressor.decompress(bytes(buff))

    async def br_decoder(app):
        buff = bytearray()
        async for chunk in app.handler():
            buff.extend(chunk)
            if len(chunk) >= 102400:
                try:
                    yield await to_thread(brotlicffi_decompress, bytes(buff))
                    buff.clear()
                except: ...
            else:
                try:
                    yield brotlicffi_decompress(bytes(buff))
                    buff.clear()
                except: ...

    async def gzip_decoder(app):
        if not app.decompressor: app.decompressor = decompressobj(16 + zlib_MAX_WBITS)

        buff = memarray()

        async for chunk in app.handler():
            buff.extend(chunk)

            if len(buff) >= 1024:
                yield app.decompressor.decompress(bytes(buff))
                buff = memarray(buff[len(buff):])

        if buff: yield app.decompressor.decompress(bytes(buff))

        if (chunk := app.decompressor.flush()):
            yield chunk

class Encoders:
    __slots__ = ()
    def __init__(app): ...

    async def br_encoder(app, data: (bytes, bytearray)):
        return await to_thread(brotlicffi_compress, bytes(data))

    async def gzip_encoder(app, data: (bytes, bytearray)):
        data = (encoder := compressobj(wbits=31)).compress(bytes(data))
        if (_ := encoder.flush()): data += _
        return data

class Async:
    @classmethod
    async def replace(app, data, a, b):
        if not a in data: return data

        idx_inc = 0
        while a in data[idx_inc:] and (idx := data.find(a)) != -1:
            idx_inc += idx + len(a)

            if data[idx:idx + len(a)] == b: break
            data = data[:idx] + b + data[idx + len(a):]

        return data

    @classmethod
    async def ite(app, data: (dict, list)):
        if isinstance(data, dict):
            for key, item in data.items():
                yield (key, item)

        elif isinstance(data, list):
            for item in data:
                yield item

    @classmethod
    async def cont(app, data: list):
        conted = ""
        for item in data:
            conted += item

        return conted

class Multipart:
    __slots__ = ("files", "kwargs", "boundary", "boundary_eof", "headers", "r", "headers_sent")

    def __init__(app, *files, **kwargs):
        app.files, app.kwargs = files, kwargs
        app.boundary = '----WebKitFormBoundary%s' % token_urlsafe(16)
        app.boundary_eof = ('\r\n%s--\r\n\r\n' % app.boundary).encode()
        app.headers = {
            "Content-Type": "multipart/form-data; boundary=%s" % app.boundary,
        }
        app.headers_sent = False

    def gen_form(app, file: (None, str) = None, filename: (None, str) = None, filetype: (None, str) = None,):
        payload = ""
        if not filename:
            filename = path.basename(file)

        if not filetype:
            filetype = guess_type(file)[0]

        for key, val in app.kwargs.items():
            payload += '%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (app.boundary, str(key), str(val))

        payload += '%s\r\nContent-Disposition: form-data; name="avatar"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (app.boundary, filename, filetype)

        return payload.encode()
    
    async def __aexit__(app, exc_type, exc_value, tb):
        if exc_value: raise exc_value
        await app.r.protocol.push(app.boundary_eof)

    async def __aenter__(app):
        app.r = ClientContext.r()
        app.r.default_writer = app.write
        return app

    async def send_headers(app, *args, headers: (bytes, bytearray, None) = None, **kwargs):
        if not headers:
            headers = app.gen_form(*args, **kwargs)

        app.headers_sent = True
        return await app.r.protocol.push(headers)

    async def write(app, *args):
        if not app.headers_sent:
            await app.send_headers(app.files[0])

        return await app.r.protocol.push(*args)

    async def ayield(app, file: str):
        async with async_open(file, "rb") as f:
            while (chunk := await f.read(OUTBOUND_CHUNK_SIZE)): yield chunk

    async def pull(app):
        for file in app.files:
            yield app.gen_form(file)

            async for chunk in app.ayield(file): yield chunk

            yield app.boundary_eof.encode()

class Formdata:
    __slots__ = ("boundary", "eof_boundary", "formdata", "header", "content_type", "content_length")
    multipart_line = "----WebKitFormBoundary"
    def __init__(app, filename: str, content_type: str, file_key: str = "file", **formdata):
        app.boundary = "%s%s" % (app.multipart_line, token_urlsafe(16)[:16])
        app.formdata = (
            *(
                'Content-Disposition: form-data; name="%s"\r\n\r\n%s' % (str(key), str(val)) if not isinstance(val, tuple) else 'Content-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (key, val[0], val[1])
                for key, val in formdata.items()
            ),
            'Content-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (file_key, filename, content_type) if (content_type is not None and file_key is not None) else '',
        )
        app.content_type = 'multipart/form-data; boundary=%s' % app.boundary
        app.header = ("\r\n".join(("--%s\r\n%s" % (app.boundary, i) for i in app.formdata if i))).encode()
        app.eof_boundary = ("\r\n--%s--\r\n" % app.boundary).encode()
        app.content_length = len(app.header + app.eof_boundary)

class AsyncHtml:
    __slots__ = ()
    def __init__(app): ...
    
    @classmethod
    async def parse_text(app, html, a: str, b: str):
        items = []

        while (idx := html.find(a)) != -1:
            item, html = html[idx + len(a):], html[idx + len(a):]

            if (idy := item.find(b)) != -1:
                item, html = item[:idy], html[idy + len(b):]
            
            if (item := item.strip()):
                items.append(item)

        return items

class Urllib:
    __slots__ = ()
    scheme_sepr: str = "://"
    host_sepr: str = "/"
    param_sepr: str = "?"
    port_sepr: str = ":"

    def __init__(app):
        ...

    @classmethod
    def url_to_host(app, url: str, params: dict, parse_params: bool = False):
        parsed_url = {}
        url = url.replace(r"\/", "/")

        if (idx := url.find(app.scheme_sepr)) != -1:
            parsed_url["hostname"] = url[idx + len(app.scheme_sepr):]

            if not app.host_sepr in parsed_url["hostname"]:
                if (idx := parsed_url["hostname"].find(app.param_sepr)) != -1:
                    parsed_url["hostname"] = parsed_url["hostname"][:idx] + app.host_sepr + parsed_url["hostname"][idx:]
                else:
                    parsed_url["hostname"] += app.host_sepr

        if (idx := parsed_url["hostname"].find(app.host_sepr)) != -1:
            parsed_url["path"], parsed_url["hostname"] = parsed_url["hostname"][idx:], parsed_url["hostname"][:idx]

        if (idx := parsed_url["hostname"].find(app.port_sepr)) != -1:
            parsed_url["port"], parsed_url["hostname"] = int(parsed_url["hostname"][idx + len(app.port_sepr):]), parsed_url["hostname"][:idx]

        if (idx := parsed_url["path"].find(app.param_sepr)) != -1:
            parsed_url["query"], parsed_url["path"] = parsed_url["path"][idx + len(app.param_sepr):], parsed_url["path"][:idx]

        host, path, port = parsed_url.get("hostname"), parsed_url.get("path"), parsed_url.get("port")

        if (query := parsed_url.get("query")):
            if parse_params:
                params.update(Request.get_params_sync(url="?%s" % query))
            else:
                path += ("?%s" % query) if "=" in query else ""

        if params:
            query = "?"
            for k, v in params.items():
                v = Request.url_encode_sync(v)
                if query == "?": x = ""
                else: x = "&"
                query += "%s%s=%s" % (x, k, v)
            path += query

        if not port:
            if url[:5].lower().startswith("https"):
                port = 443
            else:
                port = 80

        return (host, port, path)

class OtherUtils:
    __slots__ = ()
    def __init__(app):
        ...
    
    @classmethod
    def gen_payload(app, method: str, headers: dict, path: str = "/", host: str = "", port: int = 0, http_version = "1.1"):
        if method not in ["CONNECT"]:
            payload = "%s %s HTTP/%s\r\n" % (method, path, http_version)
        else:
            payload = "%s %s:%s HTTP/%s\r\n" % (method.upper(), host, port, http_version)

        for key in headers:
            payload += "%s: %s\r\n" % (key, headers[key])

        payload += "\r\n"
        return payload.encode()

if not ioConf.url_to_host:
    get_event_loop().create_task(log.critical("Using pure python implementation of: %s, which is %sX slower." % ("url_to_host", "3.0")))

    ioConf.url_to_host = Urllib.url_to_host

if not ioConf.gen_payload:
    get_event_loop().create_task(log.critical("Using pure python implementation of: %s, which is %sX slower." % ("gen_payload", "6.6")))

    ioConf.gen_payload = OtherUtils.gen_payload

class Inchunked:
    __slots__ = ("r")
    def __init__(app, r):
        app.r = r

    async def __aenter__(app):
        return app

    async def __aexit__(app, *args):
        await app.r.eof()
        if args[1]: raise args[1]

class Extractors:
    __slots__ = ()
    def __init__(app): ...

    @classmethod
    async def aread_partial(cls, app, start: (bytes, bytearray), end: (bytes, bytearray), cont = False, decode = False):
        buff, started = bytearray(), 0

        async for chunk in app.pull():
            buff.extend(chunk)

            if not started:
                if (idx := buff.find(start)) == -1:
                    buff = buff[-len(start):]
                    continue

                started = 1

                if not cont:
                    idx += len(start)

                buff = buff[idx:]

            if (ide := buff.find(end)) == -1: continue

            if cont:
                ide += len(end)

            buff = buff[:ide]
            break

        if decode:
            buff = buff.decode()

        return buff

    @classmethod
    async def stream_partial(cls, app, start: (bytes, bytearray), end: (bytes, bytearray), cont = False):
        buff, started, ended = bytearray(), 0, 0

        async for chunk in app.pull():
            if not started:
                buff.extend(chunk)
                if (idx := buff.find(start)) == -1:
                    buff = buff[-len(start):]
                    continue
                
                started = 1

                if not cont:
                    idx += len(start)

                chunk, buff = bytes(memoryview(buff)[idx:]), None

            if (ide := chunk.find(end)) != -1:
                ended = 1
                if cont:
                    ide += len(end)
                chunk = chunk[:ide]
            
            yield chunk

            if ended: break

    @classmethod
    async def find(cls, app, *args):
        data, start, end, cont = args
        while (idx := data.find(start)) != -1:
            data = data[idx + len(start):]

            if (ids := data.find(end)) != -1:
                chunk, data = data[:ids], data[ids + len(end):]

                if start in chunk:
                    async for i in app.find(chunk, *args[1:]):
                        yield (start + i + end if cont else i, data)
                else:
                    yield (start + chunk + end if cont else chunk, data)
    
    @classmethod
    async def aextract(cls, app, start: (bytes, bytearray), end: (bytes, bytearray), cont=True):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)
            async for x, data in app.find(data, start, end, cont):
                yield x

    @classmethod
    async def extract(cls, app, *args, **kwargs):
        async for chunk in app.aextract(*args, **kwargs):
            return chunk

class Extrautils:
    __slots__ = ()
    utils = (Extractors(),)
    def __init__(app):
        ...

    def __getattr__(app, key, *_args):
        for util in app.utils:
            if (val := getattr(util, key, None)):
                return val

        def method(*args, **kwargs):
            func = getattr(Request, key, None)
            if not func: raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, key))

            if func.__name__.startswith("url_"):
                if "Session" in args[0].__class__.__name__ or ClientContext.is_prot(args[0]):
                    args = args[1:]

            return func(*args, **kwargs)

        return method

class StaticStuff:
    __slots__ = ()
    
    dynamic_attrs = {
        "headers": "response_headers"
    }

    def __init__(app):
        ...

class Parsers:
    __slots__ = ()
    handle_chunked_endsig =  b"0\r\n\r\n"
    handle_chunked_sepr1 = b"\r\n"
    def __init__(app): ...

    def is_prepared(app): return True if app.status_code and app.handler else False

    def raw_cookies(app):
        cookies = ""
        if (Cookies := app.response_headers.get("set-cookie")):
            if not isinstance(Cookies, list):
                Cookies = [Cookies]

            splitter = "="
            for cookie in Cookies:
                key, val = (parts := cookie[:cookie.find(";")].split(splitter))[0], splitter.join(parts[1:])
                
                if cookies:
                    cookies += "; "

                cookies += "%s=%s" % (key, val)

        return cookies

    def dict_cookies(app, source = None):
        if not source:
            source = app.response_headers.get("set-cookie")

        cookies = ddict()
        if (Cookies := source):
            if not isinstance(Cookies, list):
                Cookies = [Cookies]

            splitter = "="
            for cookie in Cookies:
                key, val = (parts := cookie[:cookie.find(";")].split(splitter))[0], splitter.join(parts[1:])
                cookies[key] = val

        return cookies

    def join_to_current_params(app, *args, **kwargs):
        args = (*args, *app.args[len(args):]) if len(app.args) > len(args) else args
        kwargs = dict(**{i:app.kwargs[i] for i in app.kwargs if i not in kwargs}, **kwargs)
        return (args, kwargs)

    def ok(app):
        return app.status_code < 300

    def redirection_url(app):
        if app.status_code in MinParsers.http.status_codes.redirection and (location := app.response_headers.get("location", None)):
            if location.startswith("/"):
                location = "%s://%s%s" % ("https" if app.port == 443 else "http", app.host, location)

            return location

    async def _prepare_http(app):
        if app.is_prepared(): return True
        if not app.protocol: raise ServerDisconnected()

        await MinParsers.client.aparse(app)

        if app.handler == app.handle_chunked:
            app.chunked_encoder = ddict()
            app.chunked_encoder.end, app.chunked_encoder.buff = False, memarray()
            app.chunked_encoder.read, app.chunked_encoder.size, app.chunked_encoder.idx = 0, False, -1
        
        if app.method in app.no_response_body_methods or app.status_code == 304:
            app.handler = NotImplemented

        if app.decode_resp:
            if (encoding := app.response_headers.pop("content-encoding", None)):
                if (decoder := getattr(app, "%s_decoder" % encoding, None)):
                    app.decoder = decoder
                else:
                    app.decoder = None
            else:
                app.decoder = None

        if app.auto_set_cookies:
            if (cookies := app.dict_cookies()):
                if not app.kwargs.get("cookies"):
                    app.kwargs["cookies"] = cookies
                else:
                    app.kwargs["cookies"].update(cookies)

        if app.follow_redirects and (app.status_code >= 300 and app.status_code <= 310) and (location := app.redirection_url()):
            if URL(location).host != app.host: app.protocol = None
            args, kwargs = app.join_to_current_params(location)
            kwargs["follow_redirects"] = True
            return await app._connector(*args, **kwargs)
        
        return True

    async def prepare_http(app):
        await app._prepare_http()

        if app.status_code == 0:
            app.protocol = None
            await app.prepare()
            return await app.prepare_http()

    async def handle_chunked(app):
        if app.chunked_encoder.end: return

        async for chunk in app.protocol.pull():
            if app.chunked_encoder.size == False:
                app.chunked_encoder.buff.extend(chunk)
                if (idx := app.chunked_encoder.buff.find(app.handle_chunked_sepr1)) == -1: continue

                if not (s := app.chunked_encoder.buff[:idx]): continue

                app.chunked_encoder.size, app.chunked_encoder.buff = int(s, 16), memarray(app.chunked_encoder.buff[idx + len(app.handle_chunked_sepr1):])

                if app.chunked_encoder.size == 0: app.chunked_encoder.end = True

                if len(app.chunked_encoder.buff) >= app.chunked_encoder.size:
                    chunk, app.chunked_encoder.buff = app.chunked_encoder.buff, memarray(app.chunked_encoder.buff[len(app.chunked_encoder.buff):])
                else:
                    chunk, app.chunked_encoder.buff = app.chunked_encoder.buff[:app.chunked_encoder.size], memarray(app.chunked_encoder.buff[len(app.chunked_encoder.buff):])

            app.chunked_encoder.read += len(chunk)

            if app.chunked_encoder.read > app.chunked_encoder.size:
                chunk_size = len(chunk) - (app.chunked_encoder.read - app.chunked_encoder.size)

                chunk, __buff__ = chunk[:chunk_size], chunk[chunk_size + 2:]
                app.protocol.prepend(__buff__)

                app.chunked_encoder.read, app.chunked_encoder.size = 0, False

            if chunk: yield chunk

            if app.chunked_encoder.end: break

    async def handle_raw(app, *args, **kwargs):
        if not app.content_length: return

        async for chunk in app.protocol.pull():
            app.received_len += len(chunk)
            yield chunk

            if app.received_len >= app.content_length: return

    def get_filename(app):
        if (content_disposition := app.headers.get("content-disposition")):
            return (filename := content_disposition[content_disposition.find(i := 'filename="') + len(i):])[:filename.find('"')]

    def gen_filename(app):
        if (idx := (ext := app.content_type[app.content_type.find("/")+1:]).find(";")) != -1:
            ext = ext[:idx]
        return "%s.%s" % (token_urlsafe(16), ext)

class Pushtools(Encoders):
    __slots__ = ()
    def __init__(app): ...

    def inchunked(app):
        return Inchunked(app)

    async def write_chunked(app, data: (tuple[bool, AsyncIterable[bytes | bytearray]])):
        if isinstance(data, (bytes, bytearray)):
            await app.protocol.push(b"%X\r\n%s\r\n" % (len(data), data))

        elif isinstance(data, AsyncIterable):
            async for chunk in data:
                await app.protocol.push(b"%X\r\n%s\r\n" % (len(chunk), chunk))

            await app.write_chunked_eof()
        else:
            raise Err("data must be AsyncIterable | bytes | bytearray")

    async def write_chunked_eof(app, data: (tuple[bool, AsyncIterable[bytes | bytearray]] | None) = None):
        if data:
            await app.write(data)

        await app.protocol.push(Parsers.handle_chunked_endsig)

    async def eof(app, *args):
        if app.default_writer == app.write_chunked:
            method = app.write_chunked_eof
        else:
            if args and args[0]:
                method = app.write
            else:
                method = None

        if method is not None: await method(*args)
        app.eof_sent = True

    async def write(app, data: (bytes, bytearray)):
        if app.encoder:
            data = await app.encoder(data)

        return await app.default_writer(data)

class Pulltools(Parsers, Decoders):
    __slots__ = ()
    _utils = Extrautils()
    def __init__(app): ...

    def __utilsgetattr__(app, key, *_args):
        if key == "utils": return app

        def method(*args, **kwargs):
            func = getattr(app._utils, key, *_args)
            return func(app, *args, **kwargs)

        return method

    async def pull(app):
        if not app.is_prepared(): await app.prepare_http()

        if app.handler == NotImplemented: return

        if not app.handler: app.handler = app.protocol.pull

        try:
            if not app.decoder:
                async for chunk in app.handler():
                    yield chunk
            else:
                async for chunk in app.decoder(): yield chunk
        except CancelledError:
            if app.protocol and app.protocol.transport and not app.protocol.transport.is_closing(): app.protocol.transport.close()
            raise
        except (GeneratorExit, StopIteration):
            return

    async def aread(app, decode=False):
        if not app.is_prepared(): await app.prepare_http()

        if app.handler == app.protocol.pull and app.protocol.__class__.__name__ == "BlazeioClientProtocol": return

        data = bytearray()
        async for chunk in app.pull(): data.extend(chunk)
        return data if not decode else data.decode()

    async def read_exactly(app, size: int, decode=False):
        data, point = memarray(size), 0
        async for chunk in app.pull():
            len_ = len(chunk)
            rem = (size-point)

            if len_ > rem:
                chunk = chunk[:rem]
                len_ = len(chunk)

            data[point: point + len_] = chunk

            point += len_
            if point >= size: break

        return data if not decode else data.decode()

    async def text(app):
        return await app.aread(True)

    async def json(app):
        if isinstance(json := loads(await app.aread(True)), dict):
            json = Dot_Dict(json)
        return json

    async def xml(app):
        if not xml_parse: raise Missingdependency("xmltodict must be installed to use this.")
        return Dot_Dict(xml_parse(await app.aread(True)))

    async def __save__(app, filepath: str, mode: str = "wb"):
        if not app.is_prepared(): await app.prepare_http()

        async with async_open(filepath, mode) as f:
            while app.received_len < app.content_length:
                async for chunk in app.pull():
                    await f.write(bytes(chunk))
                    yield 1

                if app.handler != app.handle_raw: break

                if app.received_len < app.content_length:
                    Range = "bytes=%s-%s" % (str(app.received_len), str(app.content_length))

                    if (_args_len := len(app.args)) >= 3:
                        headers = ddict(app.args[2])
                        headers["Range"] = Range
                        if _args_len > 3:
                            app.args = (*app.args[:2], headers, *app.args[3:])
                        else:
                            app.args = (*app.args[:2], headers)

                    elif (headers := app.kwargs.get("headers")):
                        headers["Range"] = Range
                        app.kwargs["headers"] = headers

                    await app.prepare(*app.args, **app.kwargs)

    async def adl(app):
        if not app.is_prepared(): await app.prepare_http()

        if app.handler == NotImplemented: return

        if app.handler == app.handle_chunked:
            async for chunk in app.pull(): yield chunk
            return

        while app.received_len < app.content_length:
            if not app.is_prepared(): await app.prepare_http()
            if app.handler == NotImplemented: return

            try:
                async for chunk in app.pull():
                    yield chunk

            except ServerDisconnected:
                if app.method not in app.NON_BODIED_HTTP_METHODS: raise

            if app.received_len < app.content_length:
                Range = "bytes=%s-%s" % (str(app.received_len), str(app.content_length))
                if (_args_len := len(app.args)) >= 3:
                    headers = ddict(app.args[2])
                    if _args_len > 3:
                        app.args = (*app.args[:2], headers, *app.args[3:])
                    else:
                        app.args = (*app.args[:2], headers)
    
                elif (headers := app.kwargs.get("headers")):
                    app.kwargs["headers"] = (headers := ddict(headers))

                headers_view = DictView(headers)
                headers_view["Range"] = Range

                await app._connector(*app.args, **app.kwargs)
            else:
                break

    async def save(app, *args, **kwargs):
        async for _ in app.__save__(*args, **kwargs): ...

    async def asave(app, *args, **kwargs):
        async for _ in app.__save__(*args, **kwargs): yield int((app.received_len / app.content_length) * 100)

    async def close(app, *args, **kwargs):
        return await app.__aexit__(*args, **kwargs)

    async def data(app):
        if not app.is_prepared(): await app.prepare_http()

        if app.handler == app.protocol.pull and app.protocol.__class__.__name__ == "BlazeioClientProtocol": return

        if app.handler == app.handle_raw and not app.content_length: return

        if app.content_type.lower().startswith("application/json"):
            func = app.json
        elif app.content_type.lower().startswith("application/xml"):
            func = app.xml
        else:
            func = app.text

        return await func()

    async def send_file(app, file_path: str, chunk_size: (bool, int) = None):
        if not chunk_size: chunk_size = ioConf.OUTBOUND_CHUNK_SIZE

        async with async_open(file_path, "rb") as f:
            while (chunk := await f.read(chunk_size)): await app.write(chunk)

    async def asend_file(app, file_path: str, chunk_size: (bool, int) = None):
        if not chunk_size: chunk_size = ioConf.OUTBOUND_CHUNK_SIZE
        async with async_open(file_path, "rb") as f:
            uploaded = 0
            size = path.getsize(file_path)
            while (chunk := await f.read(chunk_size)):
                await app.write(chunk)
                uploaded += len(chunk)
                yield ((uploaded / size) * 100)

    async def drain_pipe(app):
        if app.pull == app.protocol.pull: return
        async for chunk in app.pull(): ...

    def __aiter__(app):
        return app.pull()

    async def pipe_to(app, pipe):
        async for chunk in app:
            if chunk: await pipe(chunk)

    async def pipe_from(app, pipe):
        async for chunk in pipe:
            if chunk: await app.write(chunk)

    async def apipe_to(app, pipe):
        async for chunk in app:
            if chunk: await pipe(chunk)
            yield int((app.received_len / app.content_length) * 100)
    
    async def read_into(app, view: memoryview):
        point, maxsize = 0, len(view)
        async for chunk in app:
            if (len(chunk) + point) > maxsize:
                _, chunk = app.protocol.prepend(chunk[(size := ((len(chunk) + point)-maxsize)):]), chunk[:size]
            view[point: (point := point + len(chunk))] = memoryview(chunk)
            if point >= maxsize: break

        return point

if __name__ == "__main__": ...
