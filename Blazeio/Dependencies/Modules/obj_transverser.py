# Blazeio.Dependencies.obj_transverser
from ...Dependencies import *

class Safe(dict):
    ...

class Obj_transverser:
    max_recursion = 5
    @classmethod
    def can_be_transversed(cls, obj):
        return hasattr(obj, "__dict__") or hasattr(obj, "__slots__") or isinstance(obj, (list, tuple))

    @classmethod
    def transverse(cls, obj, recursive = 0):
        if recursive >= cls.max_recursion: return str(obj)

        if isinstance(obj, (list,)):
            return [cls.transverse(val, 0) if cls.can_be_transversed(val) else str(val) for val in obj]

        elif isinstance(obj, dict):
            return {key: cls.transverse(val, 0) if cls.can_be_transversed(val) else str(val) for key, val in obj.items()}

        elif hasattr(obj, "__dict__") and hasattr(obj.__dict__, "items"):
            return {key: cls.transverse(val, recursive + 1) if cls.can_be_transversed(val) else str(val) for key, val in obj.__dict__.items()}

        elif hasattr(obj, "__slots__"):
            return {key: cls.transverse(val, recursive + 1) if cls.can_be_transversed(val := getattr(obj, key)) else str(val) for key in obj.__slots__}

        else:
            return str(obj)
