from ..Dependencies import p, Err, dt, Log, dumps, loads, JSONDecodeError

from .streaming import Stream, Deliver, Abort
from .safeguards import SafeGuards

class Request:
    @classmethod
    async def stream_chunks(app, r):
        if "buffered_chunks" in r.__dict__:
            yield r.buffered_chunks

        async for chunk in r.request():
            yield chunk

    @classmethod
    async def set_method(app, r, chunk):
        if not (a := b' ') in chunk:
            print(chunk)
            return

        parts = chunk.split(a)

        r.method = parts[0].decode("utf-8")
        r.tail = parts[1].decode("utf-8")

        if (c := "?") in r.tail:
            r.path = r.tail.split(c)[0]
        else:
            r.path = r.tail

        if len(parts) <= 2: return

        other_parts = a.join(parts[2:]).decode("utf-8")

        if (head_split := '\r\n') in other_parts:
            sepr = ': '
            for i in other_parts.split(head_split):
                if sepr in i:
                    key, val = i.split(sepr)
                    r.headers[key] = val
        else:
             return

    @classmethod
    async def set_data(app, r):
        r.buffered_chunks = b""
        async for chunk in app.stream_chunks(r):
            if chunk:
                r.buffered_chunks += chunk

                if (part_one := b"\r\n\r\n") in r.buffered_chunks:
                    all_ = r.buffered_chunks.split(part_one)
                    first = all_[0]
                    
                    r.buffered_chunks = part_one.join(all_[1:])
                    
                    await app.set_method(r, first)
                    break

        return r

    @classmethod
    async def get_json(app, r):
        temp = b""
        async for chunk in app.stream_chunks(r):
            if not chunk: chunk = b''
            r.buffered_chunks += chunk
            if chunk:
                temp += chunk

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
    async def get_form_data(app, r):
        sepr = b'\r\n\r\n'
        signal = b'Content-Type: '

        temp = b''
        parts = b''
        ready = True

        async for chunk in app.stream_chunks(r):
            if not chunk: chunk = b""
            if signal in chunk and temp == b'':
                chunk = signal.join(chunk.split(signal)[1:])

            temp += chunk

            if signal in temp:
                temp = temp.split(signal)
                parts = temp[0] + signal

                temp = temp[-1]

                if parts != b'' and sepr in temp:
                    _ = temp.split(sepr)
                    parts += _[0]
                    #r.buffered_chunks = _[-1]
                    break

        sepr = b'------'

        if not sepr in parts:
            return None
        else:
            parts = parts.decode("utf-8")
            sepr = sepr.decode("utf-8")

        parts = parts.split(sepr)
        json_data = {}

        for part in parts:
            start = 'form-data; name="'
            mid = '"\r\n\r\n'
            end = '\r\n'

            if start in part and mid in part and end in part:
                buff = part.split(start)[1]
                name, value = buff.split(mid)
                value = value.replace(end, '')
                json_data[name] = value

        return json_data
        
    @classmethod
    async def get_upload(app, r):
        y = 0
        
        a = b"Content-Type: "
        b = b'multipart/form-data; boundary=----WebKitFormBoundary'
        c = b'form-data'
        d = b'\r\n\r\n'
        
        ready = False

        async for chunk in app.stream_chunks(r):
            if chunk:
                if not ready:
                    if b in chunk:
                        chunk = chunk.split(b)[-1]
                    
                    if c in chunk: chunk = chunk.split(c)[-1]
    
                    if a in chunk: chunk = chunk.split(a)[-1]
                    
                    if d in chunk: chunk = d.join(chunk.split(d)[1:])
                    ready = True

                yield chunk
            else:
                y += 1
                if y > 1000: break

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
                if (y := "=" ) in param:
                    _key, value = param.split(y)
                    temp[_key] = value.replace("%20", " ")

        return temp

if __name__ == "__main__":
    pass