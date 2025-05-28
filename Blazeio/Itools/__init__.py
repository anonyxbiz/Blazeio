from secrets import token_urlsafe

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

if __name__ == "__main__": pass