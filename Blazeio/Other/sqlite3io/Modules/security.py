# ./Other/sqlite3io/Modules/security.py
from hmac import new as hmac_new, compare_digest
from hashlib import sha256
from time import time

class SignatureClient:
    __slots__ = ("key",)
    def __init__(app, key: str):
        app.key = key.encode()

    def sign(app, payload: (str, bytes)):
        if not app.key: return app.key

        if not isinstance(payload, bytes):
            if not isinstance(payload, str):
                payload = str(payload)
            payload = payload.encode()

        return hmac_new(app.key, payload, sha256).hexdigest()

    def verify(app, sign: str, payload: bytes):
        if not app.key: return True

        return compare_digest(hmac_new(app.key, payload, sha256).hexdigest(), sign)

    def get_current_timestamp(app, window_seconds: int = (5*60)):
        current_time = int(time())
        return current_time - (current_time % window_seconds)

if __name__ == "__main__":
    import Blazeio as io
    import Blazeio.Other.class_parser as class_parser

    class SignatureClientApp:
        __slots__ = ()
        def __init__(app, secret_key: (str, io.Utype, class_parser.Positional) = None, payload: (str, io.Utype, class_parser.Positional) = None):
            ...
    
    args = class_parser.Parser(SignatureClientApp, str).args()

    io.ioConf.run(io.plog.b_green(SignatureClient(args.secret_key).sign(args.payload)))