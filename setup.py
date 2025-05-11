from setuptools import setup, find_packages, Extension
from datetime import datetime as dt
from os import environ, getcwd, path, system

data_path = path.abspath(path.dirname(__file__))

with open("%s/requirements.txt" % data_path) as f:
    requirements = f.read().splitlines()

with open("%s/README.md" % data_path, encoding="utf-8") as f:
    long_description = f.read()

version = "2.1.3.5"

system("cd Blazeio/Extensions && python setup_build.py build --mname Blazeio_iourllib --mpath iourllib.c && python setup_build.py install --mname Blazeio_iourllib --mpath Blazeio_iourllib.c")

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