from setuptools import setup, find_packages, Extension
from datetime import datetime as dt
from os import environ, getcwd, path

data_path = path.abspath(path.dirname(__file__))

with open("%s/requirements.txt" % data_path) as f:
    requirements = f.read().splitlines()

with open("%s/README.md" % data_path, encoding="utf-8") as f:
    long_description = f.read()

version = "2.1.3.4"

ext_modules = []
ext_modules.append(Extension(
    'Blazeio._c_client_http_modules',
    sources=['Blazeio/Extensions/_c_client_http_modules.c'],
    extra_compile_args=['-O3'],
    define_macros=[('NDEBUG', '1')],
))

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
    ext_modules=ext_modules,
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
    },
    options={
        'build_ext': {
            'inplace': True,
            'force': True
        }
    },
    zip_safe=False,
)