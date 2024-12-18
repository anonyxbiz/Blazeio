from argparse import ArgumentParser
import importlib.util
from sys import modules

parser = ArgumentParser(prog="Blazeio", description="Web Framework")
parser.add_argument('-path', '--path', required=True, help='The path of the file')
parser.add_argument('-HOST', '--host', required=True, help='Host address to bind')
parser.add_argument('-PORT', '--port', required=True, help='Port number to bind')

args = parser.parse_args()

spec = importlib.util.spec_from_file_location("web_module", args.path)
module = importlib.util.module_from_spec(spec)
modules["web_module"] = module

spec.loader.exec_module(module)

if hasattr(module, "web"):
    web = module.web
    web.runner(args.host, int(args.port))
else:
    print("Error: 'web' object not found in the specified module.")
