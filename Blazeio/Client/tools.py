from ..Dependencies import *
from ..Modules.request import *

class StaticStuff:
    __slots__ = ()
    
    dynamic_attrs = {
        "headers": "response_headers"
    }

    def __init__(app):
        pass

class Urllib:
    __slots__ = ()
    def __init__(app):
        pass

    async def url_to_host(app, url: str, scheme_sepr: str = "://", host_sepr: str = "/", param_sepr: str = "?", port_sepr: str = ":"):
        parsed_url = {}
        
        url = url.replace(r"\/", "/")
        
        if (idx := url.find(scheme_sepr)) != -1:
            parsed_url["hostname"] = url[idx + len(scheme_sepr):]
            
            if not host_sepr in parsed_url["hostname"]:
                parsed_url["hostname"] += host_sepr

            if (idx := parsed_url["hostname"].find(host_sepr)) != -1:
                parsed_url["path"], parsed_url["hostname"] = parsed_url["hostname"][idx:], parsed_url["hostname"][:idx]

            if (idx := parsed_url["hostname"].find(port_sepr)) != -1:
                parsed_url["port"], parsed_url["hostname"] = int(parsed_url["hostname"][idx + len(port_sepr):]), parsed_url["hostname"][:idx]

            if (idx := parsed_url["path"].find(param_sepr)) != -1:
                parsed_url["query"], parsed_url["path"] = parsed_url["path"][idx + len(param_sepr):], parsed_url["path"][:idx]

        host = parsed_url.get("hostname")
        path = parsed_url.get("path")
        port = parsed_url.get("port")
        
        if (query := parsed_url.get("query")):
            params = await Request.get_params(url="?%s" % query)
            query = "?"
    
            for k,v in params.items():
                v = await Request.url_encode(v)
    
                if query == "?": x = ""
                else: x = "&"
    
                query += "%s%s=%s" % (x, k, v)
    
            path += query

        if not port:
            if url.startswith("https"):
                port = 443
            else:
                port = 80
        
        return host, port, path

class Parsers:
    __slots__ = ()
    prepare_http_sepr1 = b"\r\n"
    prepare_http_sepr2 = b": "
    prepare_http_header_end = b"\r\n\r\n"
    handle_chunked_endsig =  b"0\r\n\r\n"
    handle_chunked_sepr1 = b"\r\n"

    def __init__(app): pass

    async def prepare_http(app):
        if app.response_headers: return

        buff, headers, idx = bytearray(), None, -1

        async for chunk in app.protocol.ayield(app.timeout):
            if not chunk: continue
            buff.extend(chunk)

            if (idx := buff.find(app.prepare_http_header_end)) != -1:
                headers, buff = buff[:idx], buff[idx + len(app.prepare_http_header_end):]

                await app.protocol.prepend(buff)
                break
        
        # if idx == -1: raise Err("Unable to prepare request.")

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

    async def handle_chunked(app):
        end, buff = False, bytearray()
        read, size, idx = 0, False, -1

        async for chunk in app.protocol.ayield(app.timeout):
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

    async def handle_raw(app):
        async for chunk in app.protocol.ayield(app.timeout):
            if app.received_len >= app.content_length: break

            if not chunk: continue
            app.received_len += len(chunk)

            yield chunk

class Pushtools:
    __slots__ = ()
    def __init__(app): pass

    def __getattr__(app, name):
        if (method := getattr(app.protocol, name, None)):
            return method

    async def push(app, *args, **kwargs):
        return await app.protocol.push(*args, **kwargs)

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

    def __getattr__(app, name):
        if (val := StaticStuff.dynamic_attrs.get(name)):
            return getattr(app, val)

        raise AttributeError("'%s' object has no attribute '%s'" % (app.__class__.__name__, name))

    async def ayield(app, *args):
        async for chunk in app.protocol.ayield(*args): yield chunk

    async def pull(app, http=True):
        if http and not app.response_headers:
            await app.prepare_http()
        
        if not app.decoder:
            async for chunk in app.handler():
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

        content_type = app.response_headers.get("content-type")
        
        if content_type.lower() == "application/json":
            func = app.json
        else:
            func = app.text

        return await func()

if __name__ == "__main__":
    pass
