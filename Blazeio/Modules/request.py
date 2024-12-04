# Blazeio.Modules.request
from ..Dependencies import p, Err, dt, Log, TimeoutError, wait_for, dumps, loads, JSONDecodeError

from .streaming import Stream, Deliver, Abort
from .safeguards import SafeGuards

class Request:
    @classmethod
    async def initate(app, r):
        r.connection_established_at = dt.now()
        r.ip_host, r.ip_port = r.response.get_extra_info('peername')

        r.headers = {}
 
        r.method, r.tail, r.path, r.params = None, None, None, {}

        r.buffered_chunks = b""
        r.stream_started = NotImplemented

    @classmethod
    async def stream_chunks(app, r, CHUNK_SIZE=1024, timeout=1):
        if not "stream_started" in r.__dict__:
            await app.initate(r)
        else:
            yield r.buffered_chunks

        while True:
            try:
                chunk = await wait_for(r.request.read(CHUNK_SIZE), timeout)

                yield chunk
            except TimeoutError:
                break
            except Exception as e:
                p(e)
                break    
    
    @classmethod
    async def set_method(app, r, chunk):
        if not (a := b' ') in chunk:
            p(chunk)
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
        async for chunk in app.stream_chunks(r):
            r.buffered_chunks += chunk
            if (part_one := b"\r\n\r\n") in r.buffered_chunks:
                all_ = r.buffered_chunks.split(part_one)
                first = all_[0]
                await app.set_method(r, first)
                break

        return r
        
    @classmethod
    async def get_json(app, r):
        temp = b""
        async for chunk in app.stream_chunks(r):
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

        async for chunk in app.stream_chunks(r, timeout=1):
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
                    r.buffered_chunks = _[-1]
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
    async def get_upload(app, r, CHUNK_SIZE=1024):
        async for chunk in app.stream_chunks(r, CHUNK_SIZE, timeout=5):
            sepr = b'\r\n\r\n'
            
            if sepr in chunk:
                chunk = sepr.join(chunk.split(sepr)[1:])
                # p(chunk)
                
            yield chunk

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
