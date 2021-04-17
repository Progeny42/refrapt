import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

setup(
    name='Refrapt',
    version='0.1.0',
    description='A tool to mirror Debian repositories for use as a local mirror.',
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/Progeny42/Refrapt",
    author="Progeny42",
    packages=find_packages(),
    py_modules=[
        'refrapt', 
        'classes', 
        'helpers'
    ],
    install_requires=[
        'Click',
        'Colorama',
        'tqdm',
        'gunzip',
        'wget'
    ],
    keywords=['Mirror'. 'Debian', 'Repository']
    entry_points='''
        [console_scripts]
        refrapt=refrapt:refrapt
    ''',
)