from secrets import token_urlsafe
from collections import deque, defaultdict, OrderedDict
from asyncio import sleep
from time import perf_counter

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

ddict = Dot_Dict

class perf_timing:
    __slots__ = ("elapsed", "rps", "_done")
    def __init__(app):
        app.initialize()

    def initialize(app):
        app.elapsed = perf_counter()
        app.rps = 0
        app._done = 0

    def __call__(app):
        app._done = 1
        app.elapsed = float(perf_counter() - app.elapsed)
        app.rps = float(1.0/float(app))
        return app

    def __float__(app):
        return float(app.elapsed)

    def __dict__(app):
        if not app._done: app.__call__()
        return ddict(elapsed = float(app), rps = app.rps)

    def get(app):
        if not app._done: app.__call__()
        return ddict(elapsed = float(app), rps = app.rps)

    def __int__(app):
        return int(app.elapsed)

    def __enter__(app):
        if app._done: app.initialize()
        return app

    def __exit__(app, exc_t, exc_v, tb):
        app.__call__()
        return False

    async def __aenter__(app):
        if app._done: app.initialize()
        return app

    async def __aexit__(app, exc_t, exc_v, tb):
        app.__call__()
        return False

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
    __slots__ = ("supers", "_super", "_class_scopes")
    def __init__(app, _super = None, _class_scopes = False):
        if _super is None or getattr(app, "_super", None): return app.resolve_init()
        app._super, app._class_scopes = _super, _class_scopes if isinstance(_class_scopes, dict) else False
        app.supers = app._super.__class__.__mro__[1:]

    def resolve_init(app):
        for _super in app.supers:
            if app._class_scopes is not False:
                app._class_scopes[_super.__name__] = Dot_Dict()

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

def add_defaults_to_parser(obj, parser, for_type):
    for arg_count, arg in enumerate(obj.__init__.__annotations__.keys()):
        arg_type = obj.__init__.__annotations__.get(arg)
        if not isinstance(arg_type, tuple) or not for_type in arg_type: continue
        parser.add_argument("-%s" % arg, "--%s" % arg, type = arg_type[0], default = obj.__init__.__defaults__[arg_count])

def load_from_type_in_locals(app, fn, __locals__, _type):
    for key in __locals__:
        if (annotation := fn.__annotations__.get(key, NotImplemented)) is not NotImplemented:
            if isinstance(annotation, tuple):
                if not any([True for ann in annotation if ann in _type]):
                    continue
            elif annotation not in _type:
                continue

            setattr(app, key, __locals__[key])

def set_from_args(app, __locals__, _type, _to = None):
    setto = _to if _to is not None else app
    if not isinstance(_type, (tuple, list)):
        _type = (_type,)

    for key in __locals__:
        if (annotation := app.__init__.__annotations__.get(key, NotImplemented)) is not NotImplemented:
            if isinstance(annotation, tuple):
                if not any([True for ann in annotation if ann in _type]):
                    continue
            elif annotation not in _type:
                continue

            setattr(setto, key, __locals__[key])

def get_from_args(app, __locals__, _type):
    if not isinstance(_type, (tuple, list)):
        _type = (_type,)
    
    args = ddict()

    for key in __locals__:
        if (annotation := app.__init__.__annotations__.get(key, NotImplemented)) is not NotImplemented:
            if isinstance(annotation, tuple):
                if not any([True for ann in annotation if ann in _type]):
                    continue
            elif annotation not in _type:
                continue

            args[key] = __locals__[key]

    return args

class DictView:
    __slots__ = ("_dict", "_capitalized",)

    def __init__(app, _dict: dict):
        app._dict = _dict
        app._capitalized = {i.capitalize(): i for i in app._dict}

    def __contains__(app, key):
        if key in app._capitalized:
            return True
        return False

    def __setitem__(app, key, value):
        if key in app._capitalized:
            app.pop(key)
        else:
            app._capitalized[key.capitalize()] = key

        app._dict[key] = value

    def __getitem__(app, key):
        return app._dict[key]

    def get(app, key, default=None):
        return app._dict.get(app._capitalized.get(key), default)

    def pop(app, key, default=None):
        return app._dict.pop(app._capitalized.get(key), default)

class dotdictView(Dot_Dict):
    """
        Perf: {'create': {'elapsed': 7.165299030020833e-05, 'rps': 13956.15166666802}, 'add_time': {'elapsed': 4.93460102006793e-05, 'rps': 20265.062888229895}, 'get_time': {'elapsed': 2.623099135234952e-05, 'rps': 38122.844332013}, 'pop_time': {'elapsed': 2.5153975002467632e-05, 'rps': 39755.148039301894}}
    """
    def __init__(app, *args, **kwargs):
        object.__setattr__(app, "_capitalized", {i.capitalize(): i for i in kwargs})
        super().__init__(*args, **kwargs)

    def __contains__(app, key):
        if key in app._capitalized:
            return True
        return False

    def __setitem__(app, key, value):
        if key in app._capitalized:
            app.pop(key)
        else:
            app._capitalized[key.capitalize()] = key
        super().__setitem__(key, value)

    def get(app, key, default = None):
        return super().get(app._capitalized.get(key), default)

    def pop(app, key, default = None):
        return super().pop(app._capitalized.get(key), default)

def ensure_dumpable(json: dict, serialize: tuple = ()):
    new = {}
    for key, val in json.items():
        if isinstance(val, (str, int, list, tuple, bool, float)):
            if isinstance(val, serialize):
                val = str(val)
            new[key] = val
        elif isinstance(val, dict):
            new[key] = ensure_dumpable(val, serialize)
        else:
            new[key] = str(val)

    return new

class AsyncSyncCompatibility:
    __slots__ = ()
    def __init__(app):
        ...

    def __await__(app):
        yield
        return

AsyncSyncCompatibilityInstance = AsyncSyncCompatibility()

if __name__ == "__main__": ...