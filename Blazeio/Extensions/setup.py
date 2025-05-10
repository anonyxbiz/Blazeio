from setuptools import setup, Extension

module = Extension(
    'BlazeioClientHTTPModules',
    sources=['BlazeioClientHTTPModules.c'],
)

setup(
    name='BlazeioClientHTTPModules',
    version='1.0',
    description='Fast HTTP payload generator',
    ext_modules=[module],
)