import Blazeio as io
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-payload", "--payload", type=int, default=1)
args = parser.parse_args()
payload = b'Hello world'*args.payload

web = io.App("0.0.0.0", 8001)
io.ioConf.INBOUND_CHUNK_SIZE = 4096

@web.add_route
async def __main_handler__(r):
    await r

    await r.writer(
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Type: text/plain\r\n'
        b'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload\r\n'
        b'X-Frame-Options: DENY\r\n'
        b'X-Content-Type-Options: nosniff\r\n'
        b'X-XSS-Protection: 1; mode=block\r\n'
        b'Referrer-Policy: no-referrer-when-downgrade\r\n'
        b'Permissions-Policy: geolocation=(self), microphone=(), camera=()\r\n'
        b'Feature-Policy: accelerometer "none"; camera "none"; geolocation "self"; microphone "none"; usb "none"\r\n'
        b'Content-Security-Policy: default-src "self"; script-src "self"; object-src "none"; style-src "self";\r\n'
        b'Cache-Control: no-store, no-cache, must-revalidate, proxy-revalidate\r\n'
        b'Pragma: no-cache\r\n'
        b'Expires: 0\r\n'
        b'Server: Blazeio\r\n'
        b'Content-length: %d\r\n\r\n' % len(payload)
    )
    await r.writer(payload)

if __name__ == "__main__":
    web.with_keepalive()
    with web:
        web.runner()