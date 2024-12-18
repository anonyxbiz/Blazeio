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
