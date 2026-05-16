# ./Other/sqlite3io/Modules/security.py
from hmac import new as hmac_new, compare_digest
from hashlib import sha256

class SignatureClient:
    __slots__ = ("key",)
    def __init__(app, key: str):
        app.key = key.encode()

    def sign(app, payload: (str, bytes)):
        if not isinstance(payload, bytes):
            if not isinstance(payload, str):
                payload = str(payload)
            payload = payload.encode()

        return hmac_new(app.key, payload, sha256).hexdigest()

    def verify(app, sign: str, payload: bytes):
        return compare_digest(hmac_new(app.key, payload, sha256).hexdigest(), sign)

if __name__ == "__main__": ...