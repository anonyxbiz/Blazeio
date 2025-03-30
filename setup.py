from setuptools import setup, find_packages
from datetime import datetime as dt
from os import environ, getcwd

data_path = ""

if 1:
    with open(f"{data_path}requirements.txt") as f:
        requirements = f.read().splitlines()
    
    with open(f"{data_path}README.md", encoding="utf-8") as f:
        long_description = f.read()
else:
    requirements = []
    long_description = ""

version = "2.0.1.8"

setup(
    name="Blazeio",
    version=version,
    description="Blazeio.",
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
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'Blazeio = Blazeio.__main__:main',
        ],
    },
)