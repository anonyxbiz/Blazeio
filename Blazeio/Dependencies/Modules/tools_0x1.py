# Blazeio.Dependencies.Modules.tools_0x1

class viewarray(bytearray):
    __slots__ = ("point",)
    def __init__(app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        app.point = 0

    def __iadd__(app, data):
        if (len(data) + app.point) > len(app):
            size = ((len(data) + app.point)-len(app))
            rem, data = data[size:], data[:size]

        memoryview(app)[app.point: (point := app.point + len(data))] = memoryview(data)
        app.point = point

        return app