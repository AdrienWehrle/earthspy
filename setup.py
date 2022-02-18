from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.org').read_text(encoding='utf-8')

setup(
    name='earthspy',
    version='0.1.0',
    description='Wrapper for sentinelhub-py services',
    long_description=long_description,  
    author='Adrien Wehrlé',
    author_email='adrien.wehrle@hotmail.fr',
    packages=find_packages(include=['earthspy', 'earthspy.*'])
)
