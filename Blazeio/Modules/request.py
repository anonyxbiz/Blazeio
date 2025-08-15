from ..Dependencies import *
from ..Dependencies.alts import DictView, plog, memarray
from .streaming import *

URL_DECODE_MAP = {"%20": " ", "%21": "!", "%22": '"', "%23": "#", "%24": "$", "%25": "%", "%26": "&", "%27": "'", "%28": "(", "%29": ")", "%2A": "*", "%2B": "+", "%2C": ",", "%2D": "-", "%2E": ".", "%2F": "/", "%30": "0", "%31": "1", "%32": "2", "%33": "3", "%34": "4", "%35": "5", "%36": "6", "%37": "7", "%38": "8", "%39": "9", "%3A": ":", "%3B": ";", "%3C": "<", "%3D": "=", "%3E": ">", "%3F": "?", "%40": "@", "%41": "A", "%42": "B", "%43": "C", "%44": "D", "%45": "E", "%46": "F", "%47": "G", "%48": "H", "%49": "I", "%4A": "J", "%4B": "K", "%4C": "L", "%4D": "M", "%4E": "N", "%4F": "O", "%50": "P", "%51": "Q", "%52": "R", "%53": "S", "%54": "T", "%55": "U", "%56": "V", "%57": "W", "%58": "X", "%59": "Y", "%5A": "Z", "%5B": "[", "%5C": "\\", "%5D": "]", "%5E": "^", "%5F": "_", "%60": "`", "%61": "a", "%62": "b", "%63": "c", "%64": "d", "%65": "e", "%66": "f", "%67": "g", "%68": "h", "%69": "i", "%6A": "j", "%6B": "k", "%6C": "l", "%6D": "m", "%6E": "n", "%6F": "o", "%70": "p", "%71": "q", "%72": "r", "%73": "s", "%74": "t", "%75": "u", "%76": "v", "%77": "w", "%78": "x", "%79": "y", "%7A": "z", "%7B": "{", "%7C": "|", "%7D": "}", "%7E": "~", "%25": "%", "%3A": ":"}

class ContentDecoders:
    __slots__ = ()
    def __init__(app): ...

    async def br_decoder(app, data):
        if len(data) >= 102400:
            data = await to_thread(brotlicffi_decompress, data)
        else:
            data = brotlicffi_decompress(data)
        return data

    async def gzip_decoder(app, data):
        data = (decompressor := decompressobj(16 + zlib_MAX_WBITS)).decompress(data)

        if (chunk := decompressor.flush()):
            data += chunk
        return data

class HTTPParser:
    header_key_val = b': '
    h_s = b'\r\n'

    @classmethod
    async def make(app, r, header):
        if (sep_idx := header.find(app.header_key_val)) != -1:
            key = header[:sep_idx]
            val = header[sep_idx + 2:]

            r.headers[key.decode("utf-8").capitalize()] = val.decode("utf-8")

    @classmethod
    async def header_parser(app, r, data):
        r.headers = {}
        while (idx := data.find(app.h_s)):
            if idx == -1:
                await app.make(r, data)
                break

            header, data = data[:idx], data[idx + 2:]

            await app.make(r, header)

class Depreciated:
    URL_DECODE_MAP = URL_DECODE_MAP
    url_encoding_map = {
        " ": "%20",
        "!": "%21",
    }

    URL_DECODE_MAP_ITEMS = URL_DECODE_MAP.items()
    URL_ENCODE_MAP_ITEMS = url_encoding_map.items()

    cache = {}
    max_cache_len = 10

    def __init__(app):
        ...

    @classmethod
    def url_encode_sync(app, rawvalue: str, func_name: str = "url_encode_sync"):
        if func_name in app.cache and rawvalue in app.cache[func_name]: return app.cache[func_name][rawvalue]

        value = rawvalue

        if len(app.cache) >= app.max_cache_len: app.cache.remove(app.cache.keys()[0])

        if not func_name in app.cache:
            app.cache[func_name] = {}

        for k, v in app.URL_DECODE_MAP.items():
            if v not in value or v in app.alphas: continue
            value = value.replace(v, k)

        if len(app.cache[func_name]) >= app.max_cache_len: app.cache[func_name].remove(app.cache[func_name].keys()[0])

        app.cache[func_name][rawvalue] = value

        return value

    @classmethod
    def url_decode_sync(app, rawvalue: str, func_name: str = "url_decode_sync"):
        if func_name in app.cache and rawvalue in app.cache[func_name]: return app.cache[func_name][rawvalue]

        value = rawvalue

        if len(app.cache) >= app.max_cache_len: app.cache.remove(app.cache.keys()[0])

        if not func_name in app.cache:
            app.cache[func_name] = {}

        for k, v in app.URL_DECODE_MAP.items():
            if k not in value: continue
            value = value.replace(k, v)

        if len(app.cache[func_name]) >= app.max_cache_len: app.cache[func_name].remove(app.cache[func_name].keys()[0])

        app.cache[func_name][rawvalue] = value

        return value

    @classmethod
    def get_params_sync(app, r=None, url: (None, str) = None, q: str = "?", o: str = "&", y: str = "="):
        temp = {}
        if r is not None:
            if (idx0 := r.tail.find(q)) == -1: return temp
            params = r.tail[idx0 + 1:]

        elif url is not None:
            if (idx0 := url.find(q)) == -1: return dict(temp)

            params = url[idx0 + 1:]

        idx: int = 0

        while True:
            if (idx := params.find(y)) != -1:
                key, value = params[:idx], params[idx + 1:]
                if (idx_end := value.find(q)) != -1:
                    pass
                elif (idx := value.find(o)) != -1:
                    value, params = value[:idx], value[idx + 1:]
                temp[app.url_decode_sync(key)] = app.url_decode_sync(value)

            if idx == -1 or idx_end != -1: break

        return dict(temp)

class Request(Depreciated):
    alphas = set([*string_ascii_lowercase, string_ascii_uppercase, *[str(i) for i in range(9)]])

    form_signal3, form_header_eof, form_data_spec, form_filename = b'\r\n\r\n', (b'Content-Disposition: form-data; name="file"; filename=', ), (b'form-data; name=', b'\r\n\r\n', b'\r\n------'), (b'filename=', b'\r\n')

    __server_config__ = dict(ioConf.default_http_server_config)

    def __init__(app):
        ...

    @classmethod
    async def get_cookie(app, r, val: str = ""):
        if not Context.is_prot(r):
            val, r = r, Context.r_sync()

        val += "="
        if not val in (cookie := r.headers.get("Cookie", "")):
            return None

        cookie_start, cookie_end = val, ";"

        if (idx := cookie.find(cookie_start)) != -1:
            cookie = cookie[idx+len(cookie_start):]

            if (idx := cookie.find(cookie_end)) != -1: cookie = cookie[:idx]

        return cookie

    @classmethod
    def get_cookie_sync(app, r, val: str = ""):
        if not Context.is_prot(r):
            val, r = r, Context.r_sync()

        val += "="
        if not val in (cookie := r.headers.get("Cookie", "")):
            return None

        cookie_start, cookie_end = val, ";"

        if (idx := cookie.find(cookie_start)) != -1:
            cookie = cookie[idx+len(cookie_start):]

            if (idx := cookie.find(cookie_end)) != -1: cookie = cookie[:idx]

        return cookie

    @classmethod
    async def read_exactly(app, r, size: int, decode=False):
        data, point = memarray(size), 0
        async for chunk in r.pull():
            len_ = len(chunk)
            rem = (size-point)

            if len_ > rem:
                chunk = chunk[:rem]
                len_ = len(chunk)

            data[point: point + len_] = chunk

            point += len_
            if point >= size: break

        return data if not decode else data.decode()

    @classmethod
    async def get_json(app, r = None, *args):
        if not r: r = Context.r_sync()
        if r.content_length:
            payload = await app.read_exactly(r, r.content_length)
        else:
            payload = bytearray()
            async for chunk in r.pull(): payload.extend(chunk)

        try: return loads(payload.decode("utf-8"))
        except JSONDecodeError: raise Err("No valid JSON found in the stream.")

    @classmethod
    async def url_decode(app, *args, value: str):
        return app.url_decode_sync(value)

    @classmethod
    async def url_encode(app, *args, value: str):
        return app.url_encode_sync(value)

    @classmethod
    async def get_params(app, *args, **kwargs):
        return app.get_params_sync(*args, **kwargs)

    @classmethod
    def params(app, r = None, *args):
        if not r: r = Context._r()

        if isinstance(r.__miscellaneous__, ddict) and (params := r.__miscellaneous__.get("params", None)) is not None: return params

        params = ddict(app.get_params_sync(r))
        if not r.__miscellaneous__:
            r.__miscellaneous__ = ddict(params=params)

        return params

    @classmethod
    async def set_method(app, r, server, chunk):
        if (idx := chunk.find(server.__server_config__["__http_request_initial_separatir__"])) != -1:
            r.method, chunk = chunk[:idx].decode("utf-8"), chunk[idx + 1:]

            if (idx1 := chunk.find(server.__server_config__["__http_request_initial_separatir__"])) != -1:
                r.tail, chunk = chunk[:idx1].decode("utf-8"), chunk[idx1 + 1:]
                if (idx2 := r.tail.find('?')) != -1:
                    r.path = r.tail[:idx2]
                else:
                    r.path = r.tail

                if server.__server_config__["__http_request_auto_header_parsing__"]:
                    await HTTPParser.header_parser(r, chunk)
                else:
                    if not r.__miscellaneous__: r.__miscellaneous__ = deque()
                    r.__miscellaneous__.append(chunk)

        if r.headers:
            if (content_length := r.headers.get("Content-length")):
                r.content_length = int(content_length)
                r.pull = r.handle_raw
            elif (transfer_encoding := r.headers.get("Transfer-encoding")):
                r.transfer_encoding = transfer_encoding
                r.pull = r.handle_chunked
            else:
                r.content_length = 0
                if not hasattr(r, "pull"):
                    r.pull = r.handle_raw

        return r
    
    @classmethod
    def buff_limit_reached(app, server, __buff__, _raise = True):
        if len(__buff__) >= server.__server_config__["__http_request_max_buff_size__"]:
            if _raise: raise Abort("You have sent too much data but you haven\"t told the server how to handle it.", 413)
            else: return True

    @classmethod
    async def prepare_http_request(app, r, server=None):
        if not server: server = app
        __buff__ = memarray()

        async for chunk in r.request():
            __buff__.extend(chunk)

            if (idx := __buff__.find(server.__server_config__["__http_request_heading_end_seperator__"])) != -1:
                __heading__, __buff__ = __buff__[:idx], b'' + __buff__[idx + server.__server_config__["__http_request_heading_end_seperator_len__"]:]

                await app.set_method(r, server, __heading__)
                
                if __buff__: r.prepend(__buff__)

                break

            elif app.buff_limit_reached(server, __buff__): ...
        
        if not r.method:
            raise Eof("Request has no headers")

        return r

    @classmethod
    async def body_or_params(app, r: (BlazeioProtocol, None) = None, *args):
        if not r: r = Context.r_sync()

        if r.method in r.non_bodied_methods:
            return app.get_params_sync(r)
        else:
            return await app.get_json(r)

    @classmethod
    async def dotdict(app, r = None, *args):
        if not r: r = Context.r_sync()
        datadict = Dot_Dict()
        if r.method not in r.non_bodied_methods:
            datadict.update(await app.get_json(r))

        datadict.update(app.get_params_sync(r))
        return datadict

    @classmethod
    async def bop(app, r = None, *args):
        if not r: r = Context.r_sync()
        if r.method in r.non_bodied_methods:
            return app.get_params_sync(r)
        else:
            return await app.get_json(r)

    @classmethod
    async def form_data(app, r: (BlazeioProtocol, None) = None, *args):
        if not r: r = Context.r_sync()
        data, json_data = memarray(), {}

        async for chunk in r.pull():
            data.extend(chunk)
            if (ide := data.rfind(app.form_header_eof[0])) != -1:
                if (ida := data.rfind(app.form_signal3)) != -1:
                    __buff__, data = data[ida + len(app.form_signal3):], data[:ida]

                    if __buff__:
                        r.prepend(b'' + __buff__)

                    r.current_length -= len(__buff__)
                    break
        
        return app.format_form_data(json_data, data)
    
    @classmethod
    def format_form_data(app, json_data, data):
        while (idx := data.find(app.form_data_spec[0])) != -1 and (idx2 := data.find(app.form_data_spec[1])) != -1 and (idx3 := data.find(app.form_data_spec[2])) != -1:
            form_name, form_value = data[idx + len(app.form_data_spec[0]):idx2][1:-1], data[idx2 + len(app.form_data_spec[1]):]

            data, form_value = form_value[form_value.find(app.form_data_spec[2]) + len(app.form_data_spec[2]):], form_value[:form_value.find(app.form_data_spec[2])]

            json_data[form_name.decode("utf-8")] = form_value.decode("utf-8")
        
        filename = (filename := data[data.find(app.form_filename[0]) + len(app.form_filename[0]):])[:filename.find(app.form_filename[1])][1:-1]

        json_data["file"] = filename.decode("utf-8")

        return json_data

    @classmethod
    async def get_form_data(app, *args, **kwargs):
        return await app.form_data(*args, **kwargs)

    @classmethod
    async def wrapper(app, target, *a, **k):
        return target(*a, **k)

# Replace python implementations with their c implementations if available
for i in (Request.url_decode_sync, Request.url_encode_sync, Request.get_params_sync):
    if (func := getattr(ioConf, i.__name__)):
        setattr(Request, "_python_impl_%s" % i.__name__, i)
        setattr(Request, i.__name__, func)
        setattr(Request, (async_method := i.__name__[:-5]), lambda *a, **k: Request.wrapper(func, *a, **k))

    else:
        setattr(ioConf, i.__name__, i)

class Multipartdemux:
    __slots__ = ("r", "headers", "buff", "boundary", "boundary_only", "header_bytes")
    boundary_eof = b"\r\n\r\n"
    boundary_eof_len = len(boundary_eof)
    boundary_start = b"----WebKitFormBoundary"
    header_start = b"\r\n"
    name_s = b"Content-Disposition: form-data; name="
    name_s = b";"

    def __init__(app, r = None):
        app.r = r
        app.header_bytes = None
        app.headers = ddict()
        app.buff = memarray()
        app.boundary = None

    async def __aexit__(app, exc_type, exc_value, tb):
        if exc_value: raise exc_value

    async def __aenter__(app):
        if not app.r:
            app.r = Context._r()
        app.r.pull = app.pull
        await app.prepare_multipart()
        return app
    
    async def prepare_multipart(app):
        idx, started = 0, 0
        async for chunk in app.r.request():
            app.buff.extend(chunk)
            if not started:
                if (idx := app.buff.find(app.boundary_start)) != -1 and (ide := app.buff.find(app.header_start)) != -1:
                    app.header_bytes, app.boundary, app.boundary_only, app.buff = app.buff[:ide], app.buff[idx:ide+len(app.header_start)], app.buff[idx:ide], memarray(app.buff[ide:])

                    started = 1
                else:
                    continue

            if (app.buff.endswith(app.boundary_eof)) or app.buff.count(app.boundary) >= app.buff.count(app.boundary_eof):
                break

        idx = app.buff.rfind(app.boundary)
        ide = app.buff[idx:].find(app.boundary_eof) + len(app.boundary_eof)

        app.header_bytes += app.buff[:idx+ide]
        app.buff = app.buff[idx + ide:]

        app.parse_header_bytes()
    
    def parse_header_bytes(app):
        header_bytes = app.header_bytes
        while (idx := header_bytes.find(app.boundary)) != -1:
            form_data = header_bytes[idx + len(app.boundary):]
            name = form_data[(idx := form_data.find(app.name_s) + len(app.name_s) + 6):]

            if (ide := name.find(app.boundary_eof)) != -1:
                form_data, name = name[ide + len(app.boundary_eof):], name[:ide]

            elif (ide := name.find(app.name_e)) != -1:
                form_data, name = name[ide + len(app.name_e):], name[:ide]

            value, form_data = form_data[:(idx := form_data.find(app.header_start))], form_data[idx + len(app.header_start):]
            
            app.headers[name[1:-1].decode()] = value.decode()

            header_bytes = form_data

    def is_eof(app, chunk):
        return bytes(memoryview(chunk)[len(chunk)-(len(app.boundary_only)+10):]).find(app.boundary_only) != -1

    def slice_trail(app, chunk):
        chunk_rem = bytes(memoryview(chunk)[:chunk.rfind(app.boundary_only)])

        return bytes(memoryview(chunk_rem)[:chunk_rem.find(app.header_start)])

    async def pull(app):
        if not app.headers:
            await app.prepare_multipart()

        if app.is_eof(app.buff):
            yield app.slice_trail(app.buff)
            return
        
        yield app.buff

        async for chunk in app.r.request():
            if app.is_eof(chunk):
                yield app.slice_trail(chunk)
                break

            yield chunk

if __name__ == "__main__":
    pass