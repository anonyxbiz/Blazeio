from ..Dependencies import iopen, guess_type, basename, getsize, exists, Log
from .request import Request
from .streaming import Abort      
from aiofiles import open as aiofilesiopen

class Simpleserve:
    headers = {
        'Server': 'Blazeio',
        'Strict-Transport-Security': 'max-age=63072000; includeSubdomains', 
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'origin-when-cross-origin'
    }
    
    def __init__(app, r, file: str, CHUNK_SIZE: int = 1024, headers={}, **kwargs):
        app.__dict__.update(locals())

        if not exists(app.file):
            raise io.Abort("Not Found", 404)
            
        app.ins = None
        
    async def __aexit__(app, ext_type, ext, tb):
        if app.ins is not None: await app.ins.close()

    async def __aenter__(app):
        await app.r.write(b"HTTP/1.1 206 Partial Content\r\n")

        file_size = getsize(app.file)

        app.headers.update({
            "Accept-Ranges": "bytes",
            "Content-Type": guess_type(app.file)[0],
            "Content-Length": file_size,
            "Content-Disposition": f'inline; filename="{basename(app.file)}"',
        })

        if range_header := app.r.headers.get('Range', None):
            byte_range = range_header.strip().split('=')[1]
            _ = byte_range.split('-')
            start = int(_[0])

            if _[-1] == "":
                end = file_size - 1
            else:
                end = int(_[-1])
            
        else:
            start, end = 0, file_size
            
        if range_header:
            app.headers["Content-Range"] = f'bytes {start}-{end}/{file_size}'
        
        app.start, app.end, = start, end

        for key, val in app.headers.items():
            await app.r.write(f"{key}: {val}\r\n".encode())

        await app.r.write(b"\r\n")

        app.ins = await aiofilesiopen(app.file, "rb")

        return app
        
    async def push(app):
        while True:
            await app.ins.seek(app.start)
            if not (chunk := await app.ins.read(app.CHUNK_SIZE)): break
            
            else: app.start += len(chunk)
                    
            await app.r.write(chunk)
            
            if app.start >= app.end: break
            
            else: await app.r.control()

    async def pull(app):
        while True:
            await app.ins.seek(app.start)
            if not (chunk := await app.ins.read(app.CHUNK_SIZE)): break
            
            else: app.start += len(chunk)
                    
            yield chunk

            if app.start >= app.end: break
            
            else: await app.r.control()
            
if __name__ == "__main__":
    pass
