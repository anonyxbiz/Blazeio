from setuptools import setup, find_packages, Extension
import os
from platform import system as platform_system

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

version = "2.9.9.2"

ext_modules = [
    Extension(
        "Blazeio.Blazeio_iourllib",
        sources=["Blazeio/Extensions/Blazeio_iourllib.c"],
        extra_compile_args=['-O3'],
    ),
    Extension(
        "Blazeio.client_payload_gen", 
        sources=["Blazeio/Extensions/client_payload_gen.c"],
        extra_compile_args=['-O3'],
    ),
    Extension(
        "Blazeio.c_request_util",
        sources=["Blazeio/Extensions/c_request_util.c"],
        extra_compile_args=['-O3'],
    ),
]

if not os.environ.get("BlazeioDev"):
    kwargs = {
        "ext_modules": ext_modules,
        "cmdclass": {},
    }
else:
    kwargs = {}

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
    },
    **kwargs
)