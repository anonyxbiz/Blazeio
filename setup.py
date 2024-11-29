from setuptools import setup, find_packages

data_path = "Blazeio/data_files/"

with open(f"{data_path}requirements.txt") as f:
    requirements = f.read().splitlines()

with open(f"{data_path}README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="Blazeio",
    version="0.0.0.5",
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
        "License :: MIT",
        "Operating System :: OS Independent",
    ],
    py_modules=['Blazeio'],
    python_requires='>=3.6',
)
