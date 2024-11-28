from ..Dependencies import iopen, guess_type, basename, getsize, exists, Log
from ..Dependencies import p, Err
from .request import Request
from .streaming import Stream, Deliver, Abort      

class StaticFileHandler:
    CHUNK_SIZE = 1024
    @classmethod
    async def serve_file(app, r, file_path, headers={}, CHUNK_SIZE=None):
        
        if not exists(file_path):
            raise Abort("File Not Found", 404, reason="Not Found")
            
        else:
            filename = basename(file_path)
            file_size = getsize(file_path)
            content_type, _ = guess_type(file_path)

            content_disposition = f'inline; filename="{filename}"'

        if range_header := r.headers.get('Range'):
            byte_range = range_header.strip().split('=')[1]
            start, end = byte_range.split('-')
            start = int(start)
            end = int(end) if end else file_size - 1
        else:
            start, end = 0, file_size - 1

        content_length = str(end - start + 1)

        if not content_type:
            content_type = "application/octet-stream"
            content_disposition = f'attachment; filename="{filename}"'

        status_code = 206 if range_header else 200
        
        reason = "Partial Content" if status_code == 206 else "OK"
        
        headers.update({
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
            "Content-Disposition": content_disposition,
            "Content-Length": content_length,
        })

        if range_header:
            headers.update(
                {
                    "Content-Range": f'bytes {start}-{end}/{file_size}'
                }
            )
        
        await Stream.init(r, headers, status=status_code, reason=reason)

        async with iopen(file_path, mode="rb") as file:
            if range_header:
                await file.seek(start)
            
            CHUNK_SIZE = CHUNK_SIZE or app.CHUNK_SIZE

            while True:
                try:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    await Stream.write(r, chunk)
                except Abort as e:
                    await Log.m(r, e)
                    raise e
                    break
                except Err as e:
                    await Log.m(r, e)
                    raise e
                    break
                except Exception as e:
                    await Log.m(r, e)
                    break

if __name__ == "__main__":
    pass
