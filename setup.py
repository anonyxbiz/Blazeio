from setuptools import setup, find_packages, Extension
from datetime import datetime as dt
from os import environ, getcwd, path, system, environ
import platform

data_path = path.abspath(path.dirname(__file__))

with open("%s/requirements.txt" % data_path) as f:
    requirements = f.read().splitlines()

with open("%s/README.md" % data_path, encoding="utf-8") as f:
    long_description = f.read()

version = "2.1.4.6"

exts = ("Blazeio_iourllib", "client_payload_gen", "c_request_util")

for ext in exts:
    if platform.system() == 'Windows':
        system("%spython %s build --mname %s --mpath %s && python %s install --mname %s --mpath %s" % ("cd %s && " % path.join(data_path, "Blazeio", "Extensions"), "setup_build.py", ext, ext + ".c", "setup_build.py", ext, ext + ".c"))
    else:
        system("python %s build --mname %s --mpath %s && python %s install --mname %s --mpath %s" % (path.join(data_path, "Blazeio", "Extensions", "setup_build.py"), ext, path.join(data_path, "Blazeio", "Extensions", ext + ".c"), path.join(data_path, "Blazeio", "Extensions", "setup_build.py"), ext, path.join(data_path, "Blazeio", "Extensions", ext + ".c")))

setup(
    name="Blazeio",
    version=version,
    description="Blazeio",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    author="Anonyxbiz",
    author_email="anonyxbiz@gmail.com",
    url="https://github.com/anonyxbiz/Blazeio",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: C",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'Blazeio = Blazeio.__main__:main',
        ],
    }
)