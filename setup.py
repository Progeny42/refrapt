import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

setup(
    name='Refrapt',
    version='0.4.10',
    description='A tool to mirror Debian repositories for use as a local mirror.',
    python_requires='>=3.9',
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/Progeny42/Refrapt",
    author="Progeny42",
    packages=find_packages(),
    data_files=[
        ("refrapt", ["refrapt/refrapt.conf.example"]),
    ],
    install_requires=[
        'Click >= 7.1.2',
        'Colorama >= 0.4.4',
        'tqdm >= 4.60.0',
        'wget >= 3.2',
        'filelock == 3.0.12',
        'tendo == 0.2.15'
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "Natural Language :: English",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation",
        "Topic :: System :: Archiving :: Mirroring"
    ],
    keywords=['Mirror', 'Debian', 'Repository'],
    entry_points={
        'console_scripts': [
            "refrapt = refrapt.refrapt:main"
        ]
    },
)
