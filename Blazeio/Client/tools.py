from ..Dependencies import *
from ..Modules.request import *

ssl_context = create_default_context()

class Async:
    @classmethod
    async def replace(app, data, a, b):
        idx_inc = 0
        while (idx := data[idx_inc:].find(a)) != -1:
            await sleep(0)
            if data[idx:idx + len(a)] == b: break
            data = data[:idx] + b + data[idx + len(a):]
            idx_inc += idx + len(b)

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
            if url.lower().startswith("https"):
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
    http_redirect_status_range = (i for i in range(300,310))

    def __init__(app): pass

    async def prepare_http(app):
        if app.response_headers: return

        buff, headers, idx = bytearray(), None, -1

        async for chunk in app.protocol.ayield(app.timeout):
            if not chunk: continue
            buff.extend(chunk)

            if (idx := buff.find(app.prepare_http_header_end)) != -1:
                headers, buff = buff[:idx], buff[idx + len(app.prepare_http_header_end):]

                if buff: await app.protocol.prepend(buff)
                break

        while headers and (idx := headers.find(app.prepare_http_sepr1)):
            await sleep(0)

            if idx != -1: header, headers = headers[:idx], headers[idx + len(app.prepare_http_sepr1):]
            else: header, headers = headers, bytearray()

            if (idx := header.find(app.prepare_http_sepr2)) == -1:
                if not app.status_code:
                    app.status_code = header[header.find(b" "):].decode().strip()

                    app.status_code = int(app.status_code[:app.status_code.find(" ")].strip())

                continue
            
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
            if (Cookies := app.headers.get("set-cookie")):
                splitter = "="
                if not app.kwargs.get("cookies"):
                    app.kwargs["cookies"] = {}

                for cookie in Cookies:
                    key, val = (parts := cookie[:cookie.find(";")].split(splitter))[0], splitter.join(parts[1:])

                    app.kwargs["cookies"][key] = val

        if all([app.follow_redirects, app.status_code in app.http_redirect_status_range, (location := app.headers.get("location", None))]):
            if len(app.args) == 3:
                url, method, headers = app.args
            elif len(app.args) == 2:
                url, method, headers = app.args, app.kwargs.pop("headers", {})
            elif len(app.args) == 1:
                url, method, headers = app.args, app.kwargs.pop("method"), app.kwargs.pop("headers", {})
            elif len(app.args) == 0:
                url, method, headers = kwargs.pop("url"), app.kwargs.pop("method"), app.kwargs.pop("headers", {})

            app.args = (location, method, headers,)

            await app.prepare()

            await app.prepare_http()

    async def prepare_connect(app, method, headers):
        buff, idx = bytearray(), -1

        async for chunk in app.protocol.ayield(app.timeout):
            if not chunk: continue
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
            if not chunk: chunk = b""

            if app.handle_chunked_endsig in buff or app.handle_chunked_endsig in chunk: end = True

            if size == False:
                buff.extend(chunk)
                if (idx := buff.find(app.handle_chunked_sepr1)) == -1: continue

                if not (s := buff[:idx]):
                    buff = buff[len(app.handle_chunked_sepr1):]
                    if (ido := buff.find(app.handle_chunked_sepr1)) != -1:
                        s = buff[:ido]
                        idx = ido
                    else:
                        if not end: continue

                size, buff = int(s, 16), buff[idx + len(app.handle_chunked_sepr1):]

                if size == 0: return

                if len(buff) >= size:
                    chunk = buff
                else:
                    chunk, buff = buff[:size], buff[size:]

            read += len(chunk)

            if read < size:
                yield chunk
            else:
                excess_chunk_size = read - size
                chunk_size = len(chunk) - excess_chunk_size

                chunk, buff = chunk[:chunk_size], bytearray(chunk[chunk_size:])

                read, size = 0, False
                yield chunk
            
            if end:
                if not buff: break

    async def handle_raw(app, *args, **kwargs):
        async for chunk in app.protocol.ayield(app.timeout, *args, **kwargs):
            if app.received_len >= app.content_length: break

            if not chunk: continue
            app.received_len += len(chunk)

            yield chunk

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
        if http and not app.response_headers:
            await app.prepare_http()

        if not app.decoder:
            async for chunk in app.handler(*args, **kwargs):
                if chunk:
                    yield chunk
        else:
            async for chunk in app.decoder():
                if chunk:
                    yield chunk

    async def aread(app, decode=False):
        data = bytearray()
        async for chunk in app.pull():
            data.extend(chunk)

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
    
    async def brotli(app):
        decompressor = await to_thread(Decompressor)
        async for chunk in app.handler():
            yield await to_thread(decompressor.decompress, bytes(chunk))

    async def gzip(app):
        decompressor = decompressobj(16 + zlib_MAX_WBITS)

        async for chunk in app.handler():
            yield decompressor.decompress(bytes(chunk))

        if (chunk := decompressor.flush()):
            yield chunk

    async def save(app, filepath: str, mode: str = "wb"):
        async with async_open(filepath, mode) as f:
            async for chunk in app.pull(): await f.write(bytes(chunk))
    
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

if __name__ == "__main__":
    pass
