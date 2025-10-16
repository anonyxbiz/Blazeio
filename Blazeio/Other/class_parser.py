# Blazeio.Other.class_parser
import Blazeio as io
from argparse import ArgumentParser

class Store_true:
    __slots__ = ()
    def __init__(app): ...

class Store(Store_true): ...

class Positional:
    __slots__ = ()
    def __init__(app): ...

class Parser(ArgumentParser):
    def __init__(app, class_ = None, type_ = None, *args, **kwargs):
        app.__parsed_args__ = None
        super().__init__(*args, **kwargs)
        if class_ and type_:
            app.add_defaults_to_parser(class_, type_)
    
    def add_defaults_to_parser(app, obj, for_type):
        for arg_count, arg in enumerate(obj.__init__.__annotations__.keys()):
            arg_type = obj.__init__.__annotations__.get(arg)
            if not isinstance(arg_type, tuple) or not for_type in arg_type: continue

            default, positional, store_true = obj.__init__.__defaults__[arg_count], Positional in arg_type, Store_true in arg_type or Store in arg_type

            if positional:
                app.add_argument(arg, type = arg_type[0])
            elif store_true:
                app.add_argument("-%s" % arg, "--%s" % arg, action = "store_true")
            else:
                app.add_argument("-%s" % arg, "--%s" % arg, type = arg_type[0], default = default)

    def __iter__(app):
        app.args()
        return app.__parsed_args__.items()

    def args(app):
        if not app.__parsed_args__:
            app.__parsed_args__ = app.parse_args().__dict__

        return app.__parsed_args__

if __name__ == "__main__": ...