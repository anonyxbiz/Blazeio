from ..Dependencies import *
from .streaming import *

class Request:
    @classmethod
    async def stream_chunks(app, r):
        async for chunk in r.request():
            yield chunk

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
            if (idx := params.find(o)) != -1:
                param, params = params[:idx], params[idx + 1:]
            else:
                param = params
            
            if (idx2 := param.find(y)) != -1:
                key, value = param[:idx2], param[idx2 + 1:]
                temp[key] = unquote(value)

            if idx == -1 or idx2 == -1:
                break

        return dict(temp)

    @classmethod
    async def set_method(app, r, chunk, sepr1 = b' '):
        if (idx := chunk.find(sepr1)) != -1:
            r.method, chunk = chunk[:idx].decode("utf-8"), chunk[idx + 1:]

            if (idx1 := chunk.find(sepr1)) != -1:
                r.tail, chunk = chunk[:idx1].decode("utf-8"), chunk[idx1 + 1:]
                if (idx2 := r.tail.find('?')) != -1:
                    r.path = r.tail[:idx2]
                else:
                    r.path = r.tail

                await app.get_headers(r, chunk)

        return r

    @classmethod
    async def get_headers(app, r, chunk, header_key_val = ': ', h_s = b'\r\n', mutate=False):
        r.headers = defaultdict(str)
        idx = 0

        while True:
            await sleep(0)
            if (idx := chunk.find(h_s)) != -1:
                header, chunk = chunk[:idx].decode("utf-8"), chunk[idx + 2:]
            else:
                header = chunk.decode("utf-8")

            if (sep_idx := header.find(header_key_val)) != -1:
                key = header[:sep_idx]
                val = header[sep_idx + 2:]
                
                r.headers[key] = val
            
            if idx == -1: break

        r.headers = dict(r.headers)
            
        if mutate:
            r.headers = MappingProxyType(r.headers)
            
    @classmethod
    async def set_data(app, r, sig = b"\r\n\r\n", max_buff_size = 102400, idx = -4):
        __buff__ = bytearray()

        async for chunk in r.request():
            if chunk:
                __buff__.extend(chunk)
                if (idx := __buff__.find(sig)) != -1:
                    await app.set_method(r, __buff__[:idx])
                    break
                elif len(__buff__) >= max_buff_size:
                    break

        r.__stream__.appendleft(b'' + __buff__[idx + 4:])

        return r

    @classmethod
    async def body_or_params(app, r):
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