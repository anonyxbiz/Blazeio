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

class MultiContext:
    __slots__ = ("contexts", "exceptions", "results")
    def __init__(app, *contexts):
        app.contexts = contexts
        app.exceptions, app.results = [], []
    
    def __len__(app):
        return len(app.contexts)

    def __iter__(app):
        for context in app.contexts:
            if context: yield context

    async def __aenter__(app):
        for context in app.contexts:
            if context: await context.__aenter__()
        return app

    async def __aexit__(app, *args):
        for context in app.contexts:
            try:
                if context: app.results.append(await context.__aexit__(*args))
            except Exception as ext:
                app.exceptions.append(ext)

        for ext in app.exceptions: raise ext

        return app.results[0]

class Ringarray(bytearray):
    __slots__ = ("point", "view")
    def __init__(app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        app.point, app.view = 0, memoryview(app)

    def extend(app, data: bytes):
        return app.__iadd__(data)
    
    def add(app, data: bytes):
        app.point += len(data)
        app.view[app.point-len(data): app.point] = memoryview(data)
        if app.point >= len(app):
            app.point = 0

    def __iadd__(app, data: bytes):
        rem = None
        if (len(data) + app.point) > len(app):
            size = ((len(data) + app.point)-len(app))
            rem, data = data[size:], data[:size]

        app.add(data)

        if rem:
            return app.__iadd__(rem)

        return app
