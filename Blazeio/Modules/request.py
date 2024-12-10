from ..Dependencies import p, Err, dt, Log, dumps, loads, JSONDecodeError, defaultdict, MappingProxyType, sleep

from .streaming import Stream, Deliver, Abort

class Request:
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
    async def get_params(app, r):
        temp = {}

        if (q := "?") in r.tail:
            _ = r.tail.split(q)

            params = "".join(_[1:])
            if not (o := "&") in params:
                params += "&"

            params = params.split(o)

            for param in params:
                await sleep(0)
                if (y := "=" ) in param:
                    _key, value = param.split(y)
                    temp[_key] = value.replace("%20", " ")

        return temp

    @classmethod
    async def set_method(app, r, chunk):
        r.__parts__ = chunk.split(b' ')
        
        r.method = r.__parts__[0].decode("utf-8")
        r.tail = r.__parts__[1].decode("utf-8")
        
        r.path = r.tail.split('?')[0]

        await app.get_headers(r)
        return r

    @classmethod
    async def get_headers(app, r, mutate=False):
        other_parts = b' '.join(r.__parts__[2:]).decode("utf-8")

        if '\r\n' in other_parts:
            sepr = ': '
            headers = defaultdict(str)
            for header in other_parts.split('\r\n'):
                await sleep(0)
                if sepr in header:
                    key, val = header.split(sepr, 1)
                    headers[key.strip()] = val.strip()
            
            r.headers = dict(headers)
            if mutate: r.headers = MappingProxyType(r.headers)
        else:
            return

    @classmethod
    async def set_data(app, r):
        r.buffered_chunks = bytearray()

        async for chunk in r.request():
            if chunk:
                r.buffered_chunks.extend(chunk)
                
                if b"\r\n\r\n" in r.buffered_chunks:
                    first, remaining = r.buffered_chunks.split(b"\r\n\r\n", 1)
                    r.buffered_chunks = remaining
                    if await app.set_method(r, first): break

        return r

    @classmethod
    async def stream_chunks(app, r, backup=False):
        if not backup: yield r.buffered_chunks

        async for chunk in r.request():
            yield chunk
                
    @classmethod
    async def get_form_data(app, r, decode=True):
        signal, signal3 = b'------WebKitFormBoundary', b'\r\n\r\n'
        idx, form_data = 0, bytearray()

        async for chunk in app.stream_chunks(r):
            if chunk:
                form_data.extend(chunk)
                if signal3 in form_data:
                    break

        form_elements = form_data.split(signal3)
        r.buffered_chunks = form_elements.pop()

        form_elements = signal3.join(form_elements)
        
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
    async def get_upload(app, r):
        signal = b'------WebKitFormBoundary'
        yield r.buffered_chunks
        
        async for chunk in r.request():
            if chunk:
                if signal in chunk:
                    yield chunk#.split(signal)[0]
                    break
                else:
                    yield chunk

        return

if __name__ == "__main__":
    pass