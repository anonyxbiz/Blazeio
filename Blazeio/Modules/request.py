from ..Dependencies import *
from .streaming import *

class HTTPParser:
    header_key_val = b': '
    h_s = b'\r\n'

    @classmethod
    async def header_parser(app, r, data: bytearray):
        r.headers = {}

        async def make(header):
            if (sep_idx := header.find(app.header_key_val)) != -1:
                key = header[:sep_idx]
                val = header[sep_idx + 2:]
                r.headers[key.decode("utf-8")] = val.decode("utf-8")

        while (idx := data.find(app.h_s)):
            if idx == -1:
                await make(data)
                break

            header, data = data[:idx], data[idx + 2:]

            await make(header)

class Request:
    URL_DECODE_MAP = {
        "%20": " ", "%21": "!", "%22": '"', "%23": "#", "%24": "$", "%25": "%", 
        "%26": "&", "%27": "'", "%28": "(", "%29": ")", "%2A": "*", "%2B": "+",
        "%2C": ",", "%2D": "-", "%2E": ".", "%2F": "/", "%30": "0", "%31": "1", 
        "%32": "2", "%33": "3", "%34": "4", "%35": "5", "%36": "6", "%37": "7",
        "%38": "8", "%39": "9", "%3A": ":", "%3B": ";", "%3C": "<", "%3D": "=",
        "%3E": ">", "%3F": "?", "%40": "@", "%41": "A", "%42": "B", "%43": "C",
        "%44": "D", "%45": "E", "%46": "F", "%47": "G", "%48": "H", "%49": "I",
        "%4A": "J", "%4B": "K", "%4C": "L", "%4D": "M", "%4E": "N", "%4F": "O",
        "%50": "P", "%51": "Q", "%52": "R", "%53": "S", "%54": "T", "%55": "U",
        "%56": "V", "%57": "W", "%58": "X", "%59": "Y", "%5A": "Z", "%5B": "[",
        "%5C": "\\", "%5D": "]", "%5E": "^", "%5F": "_", "%60": "`", "%61": "a",
        "%62": "b", "%63": "c", "%64": "d", "%65": "e", "%66": "f", "%67": "g",
        "%68": "h", "%69": "i", "%6A": "j", "%6B": "k", "%6C": "l", "%6D": "m",
        "%6E": "n", "%6F": "o", "%70": "p", "%71": "q", "%72": "r", "%73": "s",
        "%74": "t", "%75": "u", "%76": "v", "%77": "w", "%78": "x", "%79": "y",
        "%7A": "z", "%7B": "{", "%7C": "|", "%7D": "}", "%7E": "~",
        "%25": "%",  # Keep %25 last to avoid double decoding issues
    }

    url_encoding_map = {
        " ": "%20",
        "!": "%21",
    }

    URL_DECODE_MAP_ITEMS = URL_DECODE_MAP.items()
    URL_ENCODE_MAP_ITEMS = url_encoding_map.items()
    
    form_signal3, form_header_eof, form_data_spec, form_filename = b'\r\n\r\n', (b'Content-Disposition: form-data; name="file"; filename=', ), (b'form-data; name=', b'\r\n\r\n', b'\r\n------'), (b'filename=', b'\r\n')


    @classmethod
    async def get_cookie(app, r, val: str):
        val += "="
        if not val in (cookie := r.headers.get("Cookie", "")):
            return None

        cookie_start, cookie_end = val, ";"

        if (idx := cookie.find(cookie_start)) != -1:
            cookie = cookie[idx+len(cookie_start):]

            if (idx := cookie.find(cookie_end)) != -1: cookie = cookie[:idx]

        return cookie

    @classmethod
    async def get_json(app, r, sepr = b'\r\n\r\n', sepr2 = b"{", sepr3 = b"}"):
        temp = bytearray()

        async for chunk in r.pull():
            temp.extend(chunk)

        try: return loads(temp.decode("utf-8"))

        except JSONDecodeError: raise Err("No valid JSON found in the stream.")

    @classmethod
    async def url_decode(app, value):
        for k, v in app.URL_DECODE_MAP_ITEMS:
            while (idx := value.find(k)) != -1:
                value = value[:idx] + v + value[idx + len(k):]
                await sleep(0)

        return value

    @classmethod
    async def url_encode(app, value):
        for k, v in app.URL_ENCODE_MAP_ITEMS:
            while (idx := value.find(k)) != -1:
                value = value[:idx] + v + value[idx + len(k):]

                await sleep(0)

        return value

    @classmethod
    async def get_params(app, r=None, url=None, q = "?", o = "&", y = "="):
        temp = defaultdict(str)
        
        if r is not None:
            if (idx0 := r.tail.find(q)) == -1: return dict(temp)
            params = r.tail[idx0 + 1:]

        elif url is not None:
            if (idx0 := url.find(q)) == -1: return dict(temp)

            params = url[idx0 + 1:]

        idx = 0
        
        while True:
            await sleep(0)

            if (idx := params.find(y)) != -1:
                key, value = params[:idx], params[idx + 1:]

                if (idx_end := value.find(q)) != -1:
                    pass
                elif (idx := value.find(o)) != -1:
                    value, params = value[:idx], value[idx + 1:]
            
            
            temp[await app.url_decode(key)] = await app.url_decode(value)

            if idx == -1 or idx_end != -1:
                break

        return dict(temp)

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

        return r

    @classmethod
    async def prepare_http_request(app, r, server):
        __buff__ = bytearray()

        async for chunk in r.request():
            if chunk:
                __buff__.extend(chunk)

            if (idx := __buff__.find(server.__server_config__["__http_request_heading_end_seperator__"])) != -1:
                __heading__, __buff__ = __buff__[:idx], b'' + __buff__[idx + server.__server_config__["__http_request_heading_end_seperator_len__"]:]

                await app.set_method(r, server, __heading__)
                
                await r.prepend(__buff__)

                break

            elif len(__buff__) >= server.__server_config__["__http_request_max_buff_size__"]:
                raise Abort("You have sent too much data but you haven\"t told the server how to handle it.", 413)
        
        if not r.method:
            raise Err("Request has no headers")

        return r

    @classmethod
    async def body_or_params(app, r=None):
        if r is None: r = await Context.r()

        if r.method in ["GET", "OPTIONS", "HEAD"]:
            return await app.get_params(r)
        else:
            return await app.get_json(r)

    @classmethod
    async def form_data(app, r = None):
        if not r: r = await Context.r()
        data = bytearray()
        json_data = defaultdict(str)

        async for chunk in r.pull():
            data.extend(chunk)
            if (ide := data.rfind(app.form_header_eof[0])) != -1:
                if (ida := data.rfind(app.form_signal3)) != -1:
                    __buff__, data = data[ida + len(app.form_signal3):], data[:ida]

                    await r.prepend(b'' + __buff__)
                    r.current_length -= len(__buff__)
                    break
        
        # await p(data)

        while (idx := data.find(app.form_data_spec[0])) != -1 and (idx2 := data.find(app.form_data_spec[1])) != -1 and (idx3 := data.find(app.form_data_spec[2])) != -1:
            await sleep(0)

            form_name, form_value = data[idx + len(app.form_data_spec[0]):idx2][1:-1], data[idx2 + len(app.form_data_spec[1]):]

            data, form_value = form_value[form_value.find(app.form_data_spec[2]) + len(app.form_data_spec[2]):], form_value[:form_value.find(app.form_data_spec[2])]

            json_data[form_name.decode("utf-8")] = form_value.decode("utf-8")
        
        filename = (filename := data[data.find(app.form_filename[0]) + len(app.form_filename[0]):])[:filename.find(app.form_filename[1])][1:-1]

        json_data["file"] = filename.decode("utf-8")
        
        # await p(json_data)
        return dict(json_data)

    @classmethod
    async def get_form_data(app, r):
        return await app.form_data(r)

if __name__ == "__main__":
    pass