from ..Dependencies import p, Err, dt, Log, dumps, loads, JSONDecodeError, defaultdict, MappingProxyType, sleep

from .streaming import Stream, Deliver, Abort

class Request:
    bad_strings = [
        "%20",     # Represents a space
        "%22",     # Double quote (")
        "%3C",     # Less-than symbol (<)
        "%3E",     # Greater-than symbol (>)
        "%3D",     # Equal sign (=)
        "%26",     # Ampersand (&)
        "%3F",     # Question mark (?)
        "%2F",     # Forward slash (/)
        "%2B",     # Plus sign (+)
        "%2C",     # Comma (,)
        "%23",     # Hash (#)
        "%25",     # Percent sign (%)
        "%2E",     # Period (.)
        "%5B",     # Opening square bracket ([)
        "%5D",     # Closing square bracket (])
        "%7B",     # Opening curly brace ({)
        "%7D",     # Closing curly brace (})
        "%3A",     # Colon (:)
        "%3B",     # Semicolon (;)
        "%40"      # At symbol (@)
    ]

    @classmethod
    async def stream_chunks(app, r):
        if r.__buff__:
            chunk = b'' + r.__buff__
            yield chunk

        cl = int(r.headers.get("Content-Length", 0))

        async for chunk in r.request():
            yield chunk

            if chunk is not None:
                r.__received_length__ += len(chunk)
            else:
                if r.__received_length__ >= cl: break

    @classmethod
    async def get_json(app, r, sepr = b'\r\n\r\n', sepr2 = b"{", sepr3 = b"}"):
        temp = bytearray()
        
        async for chunk in app.stream_chunks(r):
            if chunk:
                temp.extend(chunk)

            if (idx := temp.find(sepr)) != -1:
                temp = temp[idx + len(sepr):]

            if sepr2 in temp and sepr3 in temp:
                try:
                    start = temp.find(sepr2)
                    
                    end = temp.rfind(sepr3) + 1
                    
                    json_bytes = temp[start:end]

                    json_data = loads(json_bytes.decode("utf-8"))
                    return json_data
                except JSONDecodeError:
                    raise Err("Malformed packets are not valid JSON.")

        raise Err("No valid JSON found in the stream.")

    @classmethod
    async def param_format(app, param: str):
        for u in app.bad_strings:
            if u in param:
                while u in param:
                    param = param.replace(u, "")
                    await sleep(0)
                    
            await sleep(0)
            
        return param
 
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
                temp[key] = value

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
    async def set_data(app, r, sig = b"\r\n\r\n", max_buff_size = 10240):
        async for chunk in r.request():
            if chunk: r.__buff__.extend(chunk)

            if (idx := r.__buff__.find(sig)) != -1:
                data, r.__buff__ = r.__buff__[:idx], r.__buff__[idx + 4:]
                
                r.__received_length__ += len(r.__buff__)

                await app.set_method(r, data)
                break

            elif len(r.__buff__) >= max_buff_size:
                # Break out of the loop if exceeds limit without the sig being found
                break

        return r

    @classmethod
    async def body_or_params(app, r):
        if r.method in ["GET", "OPTIONS", "HEAD"]:
            return await app.get_params(r)
        else:
            return await app.get_json(r)


    @classmethod
    async def get_form_data(app, r, start = b'form-data; name="', middle = b'"\r\n\r\n', end = b'\r\n', filename_begin = b'file"; filename="', filename_end = b'"\r\n', content_type = b'Content-Type: ', signal = b'------WebKitFormBoundary', signal3 = b'\r\n\r\n', multipart_end = b'--\r\n'
        ):
        idx, form_data = 0, bytearray()
        
        async for chunk in app.stream_chunks(r):
            if chunk is not None:
                form_data.extend(chunk)
            
            if (idx := form_data.rfind(signal3)) != -1:
                r.__buff__, form_data = form_data[idx + len(signal3):], form_data[:idx]
                break

        json_data = defaultdict(str)
        
        while True:
            await sleep(0)
            if (dx := form_data.find(signal)) != -1:
                element, form_data = form_data[:dx], form_data[dx + len(signal):]
            else:
                element = form_data
                
            if start in element and end in element:
                _ = element.split(start).pop().split(middle)
                
                key = _[0]

                if filename_begin in key and filename_end in key and content_type in key:
                    fname, _type = key.split(filename_begin).pop().split(filename_end)
                    json_data["filename"] = fname.decode("utf-8")
                    json_data["Content-Type"] = (_type := _type.split(content_type).pop().decode("utf-8"))
                    
                    if (idx := json_data["Content-Type"].rfind(":")) != -1: json_data["Content-Type"] = json_data["Content-Type"][idx + 1:]
                    
                else:
                    value = _[-1]
                    if end in value: value = value.split(end).pop(0)
                    json_data[key.decode("utf-8")] = value.decode("utf-8")
            
            if dx == -1:
                break
            
        json_data = dict(json_data)
        return json_data

    @classmethod
    async def get_upload(app, r, *args):
        signal = b'------WebKitFormBoundary'

        async for chunk in app.stream_chunks(r, *args):
            if chunk:
                if signal in chunk:
                    yield chunk.split(signal)[0]
                    break
                else:
                    yield chunk

if __name__ == "__main__":
    pass