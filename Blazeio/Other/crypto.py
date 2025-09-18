import Blazeio as io

class Ciphen:
    __slots__ = ("key",)
    def __init__(app, key: bytes):
        app.key = key
        if not isinstance(app.key, bytes):
            app.key = app.key.encode()

    def encrypt(app, data: bytes):
        return bytes([byte ^ app.key[i % len(app.key)] for i, byte in enumerate(data)])

    def decrypt(app, data: bytes):
        return app.encrypt(data)

io.Scope.Ciphen = Ciphen

if __name__ == "__main__": ...