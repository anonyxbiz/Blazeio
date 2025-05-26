version = "1.2.3.3"

from argparse import ArgumentParser
parser = ArgumentParser(prog="Setup", description = "Setup")

for query, _type in (("mname", str), ("mpath", str)):
    parser.add_argument('-%s' % query, '--%s' % query, type = _type, required = True)

args, unknown = parser.parse_known_args()

from sys import argv
argv[1:] = unknown

from setuptools import setup, Extension
from os import path as ospath, environ

setup_script = ospath.join(abspath := (path := ospath.abspath(ospath.dirname(__file__))), "setup_build.py")

with open(setup_script, "rb") as f:
    code = (f.read()).decode()
    _version_ = ".".join(list(str(int(str((_version_ := code[(idx := code.find(version_code := 'version = "')) + len(version_code):])[:(ide := _version_.find('"'))]).replace(".", "")) + 1)))

    code = code[:idx] + version_code + str(_version_) + code[idx + len(version_code) + ide:]
    version = _version_

with open(setup_script, "wb") as f: f.write(code.encode())

ext_modules = []
ext_modules.append(Extension(
    args.mname,
    sources=[args.mpath],
    extra_compile_args=['-O3'],
))

setup(
    name = args.mname,
    version = version,
    description = args.mname,
    ext_modules = ext_modules,
    options={
        'build_ext': {
            'inplace': False if environ.get("BlazeioDev", None) else True,
            'force': True
        }
    },
)