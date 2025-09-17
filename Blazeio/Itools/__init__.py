from secrets import token_urlsafe
from collections import deque, defaultdict, OrderedDict
from asyncio import sleep

class Dot_Dict_Base(dict):
    def __setattr__(app, key, value):
        return app.__setitem__(key, value)

    def __getattr__(app, *args):
        if args[0] == "_dict": return app
        return super().__getitem__(*args)

class Dot_Dict(Dot_Dict_Base):
    ...

class DotDict(Dot_Dict_Base):
    __slots__ = ()
    def __init__(app, dictionary: (dict, None) = None, **kw):
        dictionary = dictionary or kw or {}
        super().__init__(**dictionary)

    def token_urlsafe(app, _len: int, *a, **kw):
        while (token := token_urlsafe(_len, *a, **kw)[:_len]) in app: ...
        return token

    async def atoken_urlsafe(app, _len: int, *a, **kw):
        while (token := token_urlsafe(_len, *a, **kw)[:_len]) in app:
            await sleep(0)
        return token

    def json(app):
        return app

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
        app.buff, app.pointer, app._resize = bytearray(buff_size), 0, _resize

    def _len(app):
        return app.pointer

    def chunk(app, size):
        if not app.pointer: return
        return app[int(app.pointer-size):app.pointer]

    def extend(app, data):
        if app._resize:
            if len(data) > int(len(app.buff)-app.pointer):
                app.buff = bytearray(app.buff) + bytearray(len(data))

        app[app.pointer:app.pointer + len(data)] = data

    def __getitem__(app, key):
        _ = memoryview(app.buff)[key]
        app.pointer -= len(_)
        return bytes(_)

    def __setitem__(app, key, value):
        memoryview(app.buff)[key] = memoryview(value)
        app.pointer += len(value)

    def __getattr__(app, key):
        return getattr(app.buff, key)

class Utype:
    __slots__ = ("_item",)
    def __init__(app, item = None):
        app._item = item

    def item(app):
        return app._item

class Unone:
    __slots__ = ("_item",)
    def __init__(app, item = None):
        app._item = item

    def item(app):
        return app._item

def load_from_locals(app, fn, __locals__, _type = Utype):
    for key in __locals__:
        if fn.__annotations__.get(key) == _type:
            setattr(app, key, __locals__[key])

class Super:
    __slots__ = ("supers", "_super")
    def __init__(app, _super = None):
        if _super is None or getattr(app, "_super", None): return app.resolve_init()
        app._super = _super
        app.supers = app._super.__class__.__mro__[1:]

    def resolve_init(app):
        for _super in app.supers:
            _super.__init__(app._super)
        return app

    def __getattr__(app, *args):
        if args[0] in app.__slots__: return None
        return app._super.__getattr__(*args)

    def __setattr__(app, *args):
        if args[0] in app.__slots__: return object.__setattr__(app, *args)
        return app._super.__setattr__(*args)

def Dotify(_dict_=None, **kwargs):
    if _dict_ is None:
        _dict_ = kwargs
    
    if isinstance(_dict_, dict):
        result = DotDict()
        for key, val in _dict_.items():
            if isinstance(val, (dict, list)):
                val = Dotify(val)
            result[key] = val
        return result
    elif isinstance(_dict_, list):
        return [Dotify(item) if isinstance(item, (dict, list)) else item 
                for item in _dict_]
    else:
        return _dict_

def load_from_type_in_locals(app, fn, __locals__, _type):
    for key in __locals__:
        if (annotation := fn.__annotations__.get(key, NotImplemented)) is not NotImplemented:
            if isinstance(annotation, tuple):
                if not any([True for ann in annotation if ann in _type]):
                    continue
            elif annotation not in _type:
                continue

            setattr(app, key, __locals__[key])

ddict = Dot_Dict

if __name__ == "__main__":
    pass