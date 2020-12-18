"""
Setup script to distribute dash-slicer.
"""

import re

from setuptools import find_packages, setup


NAME = "dash-slicer"
SUMMARY = "A volume slicer for Dash"


with open(f"{NAME.replace('-', '_')}/__init__.py") as fh:
    VERSION = re.search(r"__version__ = \"(.*?)\"", fh.read()).group(1)


with open("requirements.txt") as fh:
    runtime_deps = [x.strip() for x in fh.read().splitlines() if x.strip()]


setup(
    name=NAME,
    version=VERSION,
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    python_requires=">=3.6.0",
    install_requires=runtime_deps,
    license="MIT",
    description=SUMMARY,
    long_description_content_type="text/markdown",
    long_description=open("README.md").read(),
    author="Plotly",
    author_email="almar.klein@gmail.com",
    url="https://github.com/plotly/dash-slicer",
    data_files=[("", ["LICENSE"])],
    zip_safe=True,  # not if we put JS in a seperate file, I think
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Software Development :: User Interfaces",
    ],
)
