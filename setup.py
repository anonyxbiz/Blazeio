from setuptools import setup, find_packages, Extension
from datetime import datetime as dt
from os import environ, getcwd, path, system, environ
from platform import system as platform_system

data_path = path.dirname(__file__)

with open("%s/requirements.txt" % data_path) as f:
    requirements = f.read().splitlines()

with open("%s/README.md" % data_path, encoding="utf-8") as f:
    long_description = f.read()

version = "3.0.6"

kwargs = dict(
    name = "blazeio",
    version = version,
    description = "Blazeio",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    license = "MIT",
    author = "Anonyxbiz",
    author_email = "anonyxbiz@gmail.com",
    url = "https://github.com/anonyxbiz/Blazeio",
    packages = find_packages(),
    include_package_data = True,
    install_requires = requirements,
    classifiers = [
        "Programming Language :: Python :: 3",
        "Programming Language :: C",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires = '>=3.6',
    entry_points = {
        'console_scripts': [
            'Blazeio = Blazeio.__main__:main',
        ],
    },
    ext_modules = [Extension(
        module,
        sources = ["/".join(["Blazeio", "Extensions", module + ".c"])],
        extra_compile_args=['-O3'],
        )
        for module in ("Blazeio_iourllib", "client_payload_gen", "c_request_util")
    ],
    options = dict(
        build_ext = dict(
            inplace = False,
            force =  True
        )
    )
)

if platform_system() == 'Windows':
    kwargs.pop("options")
    for module in kwargs.pop("ext_modules"):
        system("%spython %s build --mname %s --mpath %s && python %s install --mname %s --mpath %s" % ("cd %s && " % path.join(data_path, "Blazeio", "Extensions"), "setup_build.py", getattr(module, "name"), path.basename(getattr(module, "sources")[0]), "setup_build.py", getattr(module, "name"), path.basename(getattr(module, "sources")[0])))

setup(**kwargs)