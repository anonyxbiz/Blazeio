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
    @classmethod
    async def get_cookie(app, r, val: str):
        if not val in (cookie := r.headers.get("Cookie", "")):
            return None

        cookie_start, cookie_end = val + "=", ";"

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
    async def get_params(app, r, q = "?", o = "&", y = "="):
        temp = defaultdict(str)
        
        if (idx0 := r.tail.find(q)) == -1: return dict(temp)

        params = r.tail[idx0 + 1:]
        idx = 0
        
        while True:
            await sleep(0)

            if (idx := params.find(y)) != -1:
                key, value = params[:idx], params[idx + 1:]

                if (idx_end := value.find(q)) != -1:
                    pass
                elif (idx := value.find(o)) != -1:
                    value, params = value[:idx], value[idx + 1:]

            temp[key] = value

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
                
                r.__stream__.appendleft(__buff__)

                break

            elif len(__buff__) >= server.__server_config__["__http_request_max_buff_size__"]:
                raise Abort("You have sent too much data but you haven\"t told the server how to handle it.", 413)
        
        if not r.method:
            raise Err("Request has no headers")

        return r

    @classmethod
    async def body_or_params(app, r=None):
        if r is None:
            r = await Context.r()

        if r.method in ["GET", "OPTIONS", "HEAD"]:
            return await app.get_params(r)
        else:
            return await app.get_json(r)

    @classmethod
    async def form_data(app, r):
        data = bytearray()
        
        sepr1 = b'Content-Disposition: form-data; '
        sepr2 = b'------'
        sepr3 = b'name="'
        sepr4 = b'"'
        signal3 = b'\r\n\r\n'
        filename = b'filename="'
        file_name_before = b'name="file";'
        file_name_after = b'name="file"'
        content_type_before = b'\r\nContent-Type:'
        content_type_after = b'name="Content-Type"'

        json_data = defaultdict(str)

        async for chunk in r.pull():
            if chunk:
                data.extend(chunk)

            if (idx := data.rfind(signal3)) != -1:
                await sleep(0)
                __buff__ = b'' + data[idx + len(signal3):]

                data = data[:idx]

                if (idx := data.find(filename)) != -1:
                    data = data[:idx] + data[idx+len(filename):]
                
                if (idx := data.find(file_name_before)) != -1:
                    data = data[:idx] + file_name_after + data[idx + len(file_name_before):]

                if (idx := data.find(content_type_before)) != -1:
                    data = data[:idx] + content_type_after + data[idx + len(content_type_before):]
                
                # await r.prepend(__buff__)

                r.__stream__.appendleft(__buff__)

                r.current_length -= len(__buff__)
                break

        if data:
            while (idx := data.find(sepr1)) != -1:
                await sleep(0)
                data = data[idx + len(sepr1):]

                if (idx := data.find(sepr2)) != -1:
                    form_data, data = data[:idx], data[idx + len(sepr2):]
                else:
                    form_data = data
                
                for name in form_data.split(sepr3):
                    if (idx := name.find(sepr4)) != -1:
                        title = name[:idx].decode("utf-8")
                        value = name[idx + len(sepr4):].strip()
                        if value.startswith(b'"'):
                            value = value[1:]
                        if value.endswith(b'"'):
                            value = value[:-1]

                        json_data[title] = value.decode("utf-8")
                        
        return dict(json_data)

    @classmethod
    async def get_form_data(app, r):
        return await app.form_data(r)

if __name__ == "__main__":
    pass