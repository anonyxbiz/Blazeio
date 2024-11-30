# Blazeio.Client
from asyncio import run, open_connection, IncompleteReadError, TimeoutError, wait_for
from ssl import create_default_context, SSLError
from json import loads
from .Dependencies import Err, p

class Client:
    APP = False

    @classmethod
    async def gen(app, url: str, method: str = "GET", headers: dict = {}, port:int = 443, connect_only=False, params=None):
        app = app()

        if params:
            prms = ""
            if not (i := "?") in url:
                prms += i
            else:
                prms += "&"

            for key, val in params.items():
                data = "%s=%s" % (str(key), str(val))
                if "=" in prms:
                    prms += "&"

                prms += data

            url += prms
        
        app.host, app.path = await app.url_to_host(url)
        
        if port == 443:
            try:
                app.ssl_context = create_default_context()
                app.response, app.request = await open_connection(app.host, port, ssl=app.ssl_context, server_hostname=app.host)
    
            except SSLError as e:
                p(e)
                raise Err("SSLError: " + str(e))
            except Exception as e:
                p(e)
                raise Err("SSLError: " + str(e))
        else:
            try:
                app.response, app.request = await open_connection(app.host, port)
            except Exception as e:
                p(e)
                raise Err("SSLError: " + str(e))

        if connect_only: return app

        await app.write(f"{method} {app.path} HTTP/1.1\r\n")

        headers["Host"] = app.host

        for key, val in headers.items():
            await app.write(f"{key}: {val}\r\n")

        await app.write("\r\n")
        return app

    async def close(app):
        try:
            app.request.close()
            await app.request.wait_closed()
        except SSLError as e:
            return
        except Exception as e:
            p(e)

    async def url_to_host(app, url):
        sepr = "://"

        if (idx := url.find(sepr)) != -1:
            url = url[idx:].replace(sepr, "")

        sepr = "/"

        if (idx := url.find(sepr)) != -1:
            path = url[idx:].replace(" ", "%20")
            url = url[:idx]

        else:
            path = sepr

        return url, path

    async def write(app, chunk):
        if isinstance(chunk, (str,)):
            chunk = chunk.encode()
        app.request.write(chunk)
        await app.request.drain()
    
    async def stream(app, chunk_size = 1024, timeout=0.5, use_timeout=True):
        count = 0
        
        while 1:
            try:
                if use_timeout:
                    chunk = await wait_for(app.response.read(chunk_size), timeout=timeout)
                else:
                    chunk = await app.response.read(chunk_size)

                if chunk == b'': break
                yield chunk
                count += 1
            except TimeoutError:
                break
            except Exception as e:
                p(e)
                break

    async def text(app, chunk_size = 1024, decode = True):
        sepr = b"\r\n\r\n"
        chunks = b""
        headers = b""
        app.resp_headers = None
        
        async for chunk in app.stream(chunk_size):
            chunks += chunk
            if not app.resp_headers and chunks.rfind(sepr) != -1:
                headers = chunks.split(sepr)[0] 
                if b"\r\n" in headers:
                    app.resp_headers = {}
                    
                    for h in headers.split(b"\r\n"):
                        h = h.decode("utf-8")
                        if ": " in h:
                            _ = h.split(": ")
                            key, val = _[0], ": ".join(_[1:])
                            
                            app.resp_headers[key] = val

        if chunks.rfind(sepr) == -1:
            return chunks

        text = sepr.join(chunks.split(sepr)[1:])
        
        if decode:
            text = text.decode("utf-8")
            
        return text
        
    async def json(app, chunk_size = 1024, decode = True):
        sepr = b"\r\n\r\n"
        chunks = b""
        headers = b""
        app.resp_headers = None
        
        async for chunk in app.stream(chunk_size):
            chunks += chunk
            if not app.resp_headers and chunks.rfind(sepr) != -1:
                headers = chunks.split(sepr)[0] 
                if b"\r\n" in headers:
                    app.resp_headers = {}
                    
                    for h in headers.split(b"\r\n"):
                        h = h.decode("utf-8")
                        if ": " in h:
                            _ = h.split(": ")
                            key, val = _[0], ": ".join(_[1:])
                            
                            app.resp_headers[key] = val

        if chunks.rfind(sepr) == -1:
            return chunks

        text = sepr.join(chunks.split(sepr)[1:])

        text = b"{".join(text.split(b"{")[1:])
        text = b"{" + text
                
        text = b"}".join(text.split(b"}")[:-1])
        text += b"}"
        
        text = text.decode("utf-8")

        text = loads(text)

        return text

class Session:
    async def __aenter__(app):
        app.app = Client
        return app.app
        
    async def __aexit__(app, exc_type, exc_val, exc_tb):
        await app.app.close()

if __name__ == "__main__":
    pass