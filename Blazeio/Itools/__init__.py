from secrets import token_urlsafe

class Dot_Dict:
    __slots__ = ("_dict",)
    def __init__(app, dictionary: (dict, None) = None, **kw):
        app._dict = dictionary or kw or {}

    def __getattr__(app, name):
        if name == "_dict": return app._dict
        if name in app._dict:
            return app._dict[name]
        else:
            return getattr(app._dict, name, None)

    def __contains__(app, key):
        if key in app._dict:
            return True
        return False

    def __setitem__(app, key, value):
        app._dict[key] = value

    def __setattr__(app, key, value):
        if key in app.__slots__:
            object.__setattr__(app, key, value)
        else:
            app._dict[key] = value

    def __getitem__(app, key):
        if key == "_dict": return app._dict
        return app._dict[key]

class DotDict:
    __slots__ = ("_dict",)
    def __init__(app, dictionary: (dict, None) = None, **kw):
        app._dict = dictionary or kw or {}

    def __getattr__(app, name):
        if name == "_dict": return app._dict
        if name in app._dict:
            return app._dict[name]
        else:
            return getattr(app._dict, name, None)

    def __contains__(app, key):
        if key in app._dict:
            return True
        return False

    def __setitem__(app, key, value):
        app._dict[key] = value

    def __setattr__(app, key, value):
        if key in app.__slots__:
            object.__setattr__(app, key, value)
        else:
            app._dict[key] = value

    def __getitem__(app, key):
        if key == "_dict": return app._dict
        return app._dict[key]

    def token_urlsafe(app, *a, **kw):
        while (token := token_urlsafe(*a, **kw)) in app._dict: pass
        return token

    def json(app):
        return app._dict

class Multirouter:
    __slots__ = ("routes", "route_name")
    def __init__(app, route_name, *routes):
        app.route_name, app.routes = route_name, [*routes]

    def add(app, route):
        app.routes.append(route)

    async def router(app, *args, **kwargs):
        for route in app.routes:
            _ = await route["func"](*args, **kwargs)

        return _

    def get_router(app):
        return {
            "func": app.router,
            "params": {},
            "len": len(app.route_name)
        }

class memarray(bytearray):
    __slots__ = ()
    def __getitem__(app, key):
        if isinstance(key, slice):
            return bytes(memoryview(app)[key])
        return super().__getitem__(key)

    def __setitem__(app, key, value):
        if isinstance(key, slice):
            memoryview(app)[key] = memoryview(value)
            return

        return super().__setitem__(key, value)

class zcbuff:
    __slots__ = ("buff", "pointer", "_resize")
    def __init__(app, buff_size: int = 4096, _resize: bool = False):
        app.buff, app.pointer, app._resize = memarray(buff_size), 0, _resize

    def extend(app, data):
        if app._resize:
            if len(data) > (len(app.buff)-app.pointer): app.buff.extend(len(data))
        app.buff[app.pointer:app.pointer + len(data)] = data
        app.pointer += len(data)

    def __getitem__(app, *args):
        _ = app.buff.__getitem__(*args)
        if app.pointer:
            app.pointer -= len(_)
        return _

    def __setitem__(app, *args):
        return app.buff.__setitem__(*args)

if __name__ == "__main__":
    pass