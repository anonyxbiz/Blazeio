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
    async def stream_chunks(app, r, MAX_BUFF_SIZE = None):
        """
            Some systems have issues when you try writing bytearray to a file, so it is better to ensure youre streaming bytes object.
        """

        yield b'' + r.__buff__

        async for chunk in r.request():
            yield chunk

    @classmethod
    async def get_json(app, r):
        temp = bytearray()
        async for chunk in app.stream_chunks(r):
            if not chunk: chunk = b''
            else: temp.extend(chunk)

            if (sepr := b'\r\n\r\n') in temp:
                temp = sepr.join(temp.split(sepr)[1:])

            if b"{" in temp and b"}" in temp:
                try:
                    start = temp.find(b"{")
                    end = temp.rfind(b"}") + 1
                    json_bytes = temp[start:end]

                    json_data = loads(json_bytes.decode())
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
    async def get_params(app, r):
        temp = defaultdict(str)

        if (q := "?") in r.tail:
            _ = r.tail.split(q)

            params = "".join(_[1:])
            if not (o := "&") in params:
                params += "&"

            for param in params.split(o):
                await sleep(0)
                if (y := "=" ) in param:
                    _key, value = param.split(y)
                    temp[_key] = await app.param_format(value)

        return dict(temp)

    @classmethod
    async def get_param(app, r, key: str):
        key += "="
        
        if not key in r.tail:
            return
        
        param = r.tail.split(key)[-1]
        
        if o := "&" in param: param = param.split(o)[0]
        
        return await app.param_format(param)

    @classmethod
    async def set_method(app, r, chunk):
        if (idx := chunk.find(b' ')) != -1:
            r.method = chunk[:idx].decode("utf-8")

            chunk = chunk[idx+1:]
            if (idx := chunk.find(b' ')) != -1:
                r.tail = chunk[:idx].decode("utf-8")
                
                if (idx2 := r.tail.find('?')) != -1:
                    r.path = r.tail[:idx2]
                else:
                    r.path = r.tail

                await app.get_headers(r, chunk)
                
                # chunk = chunk[idx+1:]

        return r

    @classmethod
    async def get_headers(app, r, chunk, header_key_val = ': ', h_s = '\r\n', mutate=False):
        chunk = chunk.decode("utf-8")

        if h_s in chunk:
            headers = defaultdict(str)
            
            for header in chunk.split(h_s):
                await sleep(0)
                
                if (idx := header.find(header_key_val)) != -1:
                    headers[header[:idx].strip()] = header[idx:].strip()

            r.headers = dict(headers)
            
            if mutate:
                r.headers = MappingProxyType(r.headers)
        else:
            return

    @classmethod
    async def set_data(app, r, sig = b"\r\n\r\n", max_buff_size = 1024):
        
        async for chunk in r.request():
            if chunk: r.__buff__.extend(chunk)

            if (idx := r.__buff__.find(sig)) != -1:
                first = r.__buff__[:idx]
                
                r.__buff__ = r.__buff__[idx + len(sig):]
                
                await app.set_method(r, first)
                
                break
            
            elif len(r.__buff__) >= max_buff_size:
                break

        return r

    @classmethod
    async def get_form_data(app, r, decode=True):
        signal, signal3 = b'------WebKitFormBoundary', b'\r\n\r\n'
        idx, form_data = 0, bytearray()

        async for chunk in app.stream_chunks(r):
            if chunk is not None:
                form_data.extend(chunk)
                
                if (idx := form_data.rfind(signal3)) != -1:
                    break

        form_elements = form_data[:idx]
        r.__buff__ = form_data[idx + len(signal3):]

        json_data = defaultdict(str)
        
        objs = (b'form-data; name="', b'"\r\n\r\n', b'\r\n')
        
        start, middle, end, filename_begin, filename_end, content_type = objs[0], objs[1], objs[2], b'file"; filename="', b'"\r\n', b'Content-Type: '

        for element in form_elements.split(signal):
            await sleep(0)
            if start in element and end in element:
                _ = element.split(start).pop().split(middle)
                
                key = _[0]

                if filename_begin in key and filename_end in key and content_type in key:
                    fname, _type = key.split(filename_begin).pop().split(filename_end)

                    json_data["filename"] = fname if not decode else fname.decode("utf-8")
                    json_data["Content-Type"] = (_type := _type.split(content_type).pop()) if not decode else _type.split(content_type).pop().decode("utf-8")
                    
                else:
                    value = _[-1]
                    if end in value: value = value.split(end).pop(0)
                    
                    json_data[key if not decode else key.decode("utf-8")] = value if not decode else value.decode("utf-8")

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