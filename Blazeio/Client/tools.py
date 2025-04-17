from ..Dependencies import *
from ..Modules.request import *

ssl_context = create_default_context()

class Rvtools:
    headers = {
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

    def __init__(app): pass

class Async:
    @classmethod
    async def replace(app, data, a, b):
        idx_inc = 0
        while a in data[idx_inc:] and (idx := data.find(a)) != -1:
            idx_inc += idx + len(a)

            await sleep(0)
            if data[idx:idx + len(a)] == b: break
            data = data[:idx] + b + data[idx + len(a):]

        return data

    @classmethod
    async def ite(app, data: (dict, list)):
        if isinstance(data, dict):
            for key, item in data.items():
                await sleep(0)
                yield (key, item)

        elif isinstance(data, list):
            for item in data:
                await sleep(0)
                yield item

    @classmethod
    async def cont(app, data: list):
        conted = ""
        for item in data:
            await sleep(0)
            conted += item

        return conted

class Multipart:
    __slots__ = ("files", "kwargs", "boundary", "boundary_eof", "headers",)

    def __init__(app, files: str, **kwargs):
        app.files, app.kwargs = files, kwargs
        app.boundary = '----WebKitFormBoundary%s' % token_urlsafe(16)
        app.boundary_eof = '\r\n%s--\r\n\r\n' % app.boundary
        app.headers = {
            "Content-Type": "multipart/form-data; boundary=%s" % app.boundary,
            "Transfer-Encoding": "chunked",
        }

    async def gen_form(app, file: str):
        filename = path.basename(file)
        filetype = guess_type(file)[0]

        for key, val in app.kwargs.items():
            yield ('%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (app.boundary, str(key), str(val))).encode()

        yield ('%s\r\nContent-Disposition: form-data; name="avatar"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (app.boundary, filename, filetype)).encode()

    async def ayield(app, file: str):
        async with async_open(file, "rb") as f:
            while (chunk := await f.read(OUTBOUND_CHUNK_SIZE)): yield chunk

    async def pull(app):
        for file in app.files:
            async for chunk in app.gen_form(file): yield chunk
    
            async for chunk in app.ayield(file): yield chunk

            yield app.boundary_eof.encode()

class AsyncHtml:
    __slots__ = ()
    def __init__(app): pass
    
    @classmethod
    async def parse_text(app, html, a: str, b: str):
        items = []

        while (idx := html.find(a)) != -1:
            await sleep(0)
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
        pass

    async def url_to_host(app, url: str, params: dict):
        parsed_url = {}

        url = await Async.replace(url, r"\/", "/")

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

        host = parsed_url.get("hostname")
        path = parsed_url.get("path")
        port = parsed_url.get("port")

        if (query := parsed_url.get("query")):
            params.update(await Request.get_params(url="?%s" % query))
        
        if params:
            query = "?"

            for k,v in params.items():
                v = await Request.url_encode(v)
    
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

class StaticStuff:
    __slots__ = ()
    
    dynamic_attrs = {
        "headers": "response_headers"
    }

    def __init__(app):
        pass

class Parsers:
    __slots__ = ()
    prepare_http_sepr1 = b"\r\n"
    prepare_http_sepr2 = b": "
    prepare_http_header_end = b"\r\n\r\n"
    handle_chunked_endsig =  b"0\r\n\r\n"
    handle_chunked_sepr1 = b"\r\n"
    http_redirect_status_range = (300,301,302,304,305,306,307,308,309)
    http_startswith = b"HTTP"

    def __init__(app): pass
    
    async def clean_transport(app):
        temp = bytearray()
        async for chunk in app.protocol.ayield(app.timeout):
            temp.extend(chunk)

            if (idx := temp.find(app.http_startswith)) == -1:
                temp = temp[-len(app.http_startswith):]
                continue
            else:
                await app.protocol.prepend(temp[idx:])
                break

    async def prepare_http(app):
        if app.response_headers: return True
        if app.consumption_started: await app.clean_transport()

        buff, headers, idx = bytearray(), None, -1

        async for chunk in app.protocol.ayield(app.timeout):
            buff.extend(chunk)
            if len(buff) >= len(app.http_startswith):
                if buff[:len(app.http_startswith)].upper() != app.http_startswith:
                    return await app.protocol.prepend(buff)

            if (idx := buff.find(app.prepare_http_header_end)) != -1:
                headers, buff = buff[:idx], buff[idx + len(app.prepare_http_header_end):]

                if buff: await app.protocol.prepend(buff)
                break
        
        if idx == -1:
            if buff: await app.protocol.prepend(buff)
            return

        if (idx := headers.find(app.prepare_http_sepr1)) != -1:
            prot_headers = headers[:idx]

            prot_headers_splits = prot_headers.decode().split(" ")

            prot, app.status_code, app.reason_phrase = prot_headers_splits[0], int(prot_headers_splits[1]), " ".join(prot_headers_splits[2:])

            headers = headers[idx + len(app.prepare_http_sepr1):]
        else:
            raise Err("Unknown Server Protocol")

        while headers:
            await sleep(0)

            if (idx := headers.find(app.prepare_http_sepr1)) != -1: header, headers = headers[:idx], headers[idx + len(app.prepare_http_sepr1):]
            else: header, headers = headers, b""

            if (idx := header.find(app.prepare_http_sepr2)) == -1: continue

            key, value = header[:idx].decode().lower(), header[idx + len(app.prepare_http_sepr2):].decode()

            if key in app.response_headers:
                if not isinstance(app.response_headers[key], list):
                    app.response_headers[key] = [app.response_headers[key]]

                app.response_headers[key].append(value)
                continue

            app.response_headers[key] = value

        app.received_len, app.content_length = 0, int(app.response_headers.get('content-length',  0))

        if app.response_headers.get("transfer-encoding"):
            app.handler = app.handle_chunked
        elif app.response_headers.get("content-length"):
            app.handler = app.handle_raw
        else:
            app.handler = app.protocol.pull

        if app.decode_resp:
            if (encoding := app.response_headers.pop("content-encoding", None)):
                if encoding == "br":
                    app.decoder = app.brotli
                elif encoding == "gzip":
                    app.decoder = app.gzip
                else:
                    app.decoder = None
            else:
                app.decoder = None

        if app.auto_set_cookies:
            if (Cookies := app.response_headers.get("set-cookie")):
                splitter = "="
                if not app.kwargs.get("cookies"):
                    app.kwargs["cookies"] = {}

                for cookie in Cookies:
                    key, val = (parts := cookie[:cookie.find(";")].split(splitter))[0], splitter.join(parts[1:])

                    app.kwargs["cookies"][key] = val

        if all([app.follow_redirects, app.status_code in app.http_redirect_status_range, (location := app.response_headers.get("location", None))]):
            await app.prepare(location)
        
        return True

    async def prepare_connect(app, method, headers):
        buff, idx = bytearray(), -1

        async for chunk in app.protocol.ayield(app.timeout):
            buff.extend(chunk)

            if (idx := buff.rfind(app.prepare_http_sepr1)) != -1: break

        if (auth_header := "Proxy-Authorization") in headers: headers.pop(auth_header)

        if app.proxy_port != 443 and app.port == 443:
            retry_count = 0
            max_retry_count = 2

            while retry_count < max_retry_count:
                try: tls_transport = await loop.start_tls(app.protocol.transport, app.protocol, ssl_context, server_hostname=app.host)
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retry_count: await log.warning("Ssl Handshake Failed multiple times...: %s" % str(e))
                    await sleep(0)
                    continue
                
                if tls_transport:
                    app.protocol.transport = tls_transport

                break

        await app.protocol.push(await app.gen_payload(method, headers, app.path))

    async def handle_chunked(app, *args, **kwargs):
        end, buff = False, bytearray()
        read, size, idx = 0, False, -1

        async for chunk in app.protocol.ayield(app.timeout, *args, **kwargs):
            if size == False:
                buff.extend(chunk)
                if (idx := buff.find(app.handle_chunked_sepr1)) == -1: continue

                if not (s := buff[:idx]): continue

                size, buff = int(s, 16), buff[idx + len(app.handle_chunked_sepr1):]

                if size == 0: end = True

                if len(buff) >= size:
                    chunk, buff = buff, bytearray()
                else:
                    chunk, buff = buff[:size], bytearray()

            read += len(chunk)

            if read <= size:
                pass
            else:
                excess_chunk_size = read - size
                chunk_size = len(chunk) - excess_chunk_size

                chunk, __buff__ = chunk[:chunk_size], bytearray(chunk[chunk_size + 2:])
                
                await app.protocol.prepend(__buff__)

                read, size = 0, False
            
            yield chunk

            if end: break

    async def handle_raw(app, *args, **kwargs):
        async for chunk in app.protocol.ayield(app.timeout, *args, **kwargs):
            app.received_len += len(chunk)

            yield chunk

            if app.received_len >= app.content_length: break

class Pushtools:
    __slots__ = ()
    def __init__(app): pass

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
        if app.write == app.write_chunked:
            method = app.write_chunked_eof
        else:
            method = None

        if method is not None: await method(*args)

class Pulltools(Parsers):
    __slots__ = ()
    def __init__(app):
        pass

    async def pull(app, *args, http=True, **kwargs):
        if not app.consumption_started:
            app.consumption_started = True

        if http and not app.response_headers: await app.prepare_http()
        
        try:
            if not app.decoder:
                async for chunk in app.handler(*args, **kwargs):
                    if chunk:
                        yield chunk
            else:
                async for chunk in app.decoder():
                    if chunk:
                        yield chunk

        except (GeneratorExit, StopIteration) as e:
            pass

    async def aread(app, decode=False):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)

        return data if not decode else data.decode()

    async def read_exactly(app, size: int, decode=False):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)
            if len(data) >= size: break

        return data if not decode else data.decode()

    async def text(app):
        return await app.aread(True)

    async def json(app):
        data = await app.aread(True)

        if len(data) >= app.max_unthreaded_json_loads_size:
            json = await to_thread(loads, data)
        else:
            json = loads(data)

        return json

    async def find(app, *args):
        data, start, end, cont = args
        while (idx := data.find(start)) != -1:
            await sleep(0)
            data = data[idx + len(start):]

            if (ids := data.find(end)) != -1:
                chunk, data = data[:ids], data[ids + len(end):]

                if start in chunk:
                    async for i in app.find(chunk, *args[1:]):
                        yield (start + i + end if cont else i, data)
                else:
                    yield (start + chunk + end if cont else chunk, data)

    async def aextract(app, start: (bytes, bytearray), end: (bytes, bytearray), cont=True):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)
            async for x, data in app.find(data, start, end, cont):
                yield x

    async def extract(app, *args, **kwargs):
        async for chunk in app.aextract(*args, **kwargs):
            return chunk

    async def brotli(app):
        if not app.decompressor:
            app.decompressor = await to_thread(Decompressor)
        async for chunk in app.handler():
            yield await to_thread(app.decompressor.decompress, bytes(chunk))

    async def gzip(app):
        if not app.decompressor:
            app.decompressor = decompressobj(16 + zlib_MAX_WBITS)

        async for chunk in app.handler():
            yield app.decompressor.decompress(bytes(chunk))

        if (chunk := app.decompressor.flush()):
            yield chunk

    async def save(app, filepath: str, mode: str = "wb"):
        async with async_open(filepath, mode) as f:
            async for chunk in app.pull(): await f.write(bytes(chunk))
            await sleep(0)

    async def close(app, *args, **kwargs): return await app.__aexit__(*args, **kwargs)
    
    async def data(app):
        if not app.response_headers: await app.prepare_http()

        content_type = app.response_headers.get("content-type", "")

        if content_type.lower() == "application/json":
            func = app.json
        else:
            func = app.text

        return await func()

    async def send_file(app, file_path: str, chunk_size: (bool, int) = None):
        if not chunk_size: chunk_size = OUTBOUND_CHUNK_SIZE

        async with async_open(file_path, "rb") as f:
            while (chunk := await f.read(chunk_size)): await app.write(chunk)
            await sleep(0)
    
    async def drain_pipe(app):
        async for chunk in app.pull(): break

if __name__ == "__main__":
    pass
