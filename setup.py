import re

from setuptools import find_packages, setup


NAME = "dash_3d_viewer"
SUMMARY = (
    "A library to make it easy to build slice-views on 3D image data in Dash apps."
)

with open(f"{NAME}/__init__.py") as fh:
    VERSION = re.search(r"__version__ = \"(.*?)\"", fh.read()).group(1)


runtime_deps = [
    "pillow",
    "numpy",
    "plotly",
    "dash",
    "dash_core_components",
    "scikit-image",  # may not be needed eventually?
]


setup(
    name=NAME,
    version=VERSION,
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    python_requires=">=3.6.0",
    install_requires=runtime_deps,
    license="MIT",
    description=SUMMARY,
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Plotly",
    author_email="almar.klein@gmail.com",
    # url="https://github.com/plotly/will be renamed?",
    data_files=[("", ["LICENSE"])],
    zip_safe=True,  # not if we put JS in a seperate file, I think
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
)
