# Blazeio.Other.class_parser
import Blazeio as io
from argparse import ArgumentParser

class Parser(ArgumentParser):
    def __init__(app, class_, type_, *args, **kwargs):
        super().__init__(*args, **kwargs)
        io.add_defaults_to_parser(class_, app, type_)

if __name__ == "__main__": ...