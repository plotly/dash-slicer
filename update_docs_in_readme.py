#!/usr/bin/env python3
"""
Run this script to update the README.md with tha current reference docs.
"""

import os
from dash_slicer.docs import get_reference_docs, md_seperator


HERE = os.path.dirname(os.path.abspath(__file__))


def write_reference_docs():
    """Write the reference docs to the README."""
    # Prepare
    filename = os.path.join(HERE, "README.md")
    assert os.path.isfile(filename), "README.md not found"
    # Load first part of the readme
    with open(filename, "rb") as f:
        text = f.read().decode()
    text1, _, _ = text.partition(md_seperator)
    text1 = text1.strip()
    # Create second part of the readme
    text2 = "\n\n" + md_seperator + "\n\n" + get_reference_docs()
    if "\r" in text1:
        text2 = text2.replace("\n", "\r\n")
    # Wite
    with open(filename, "wb") as f:
        f.write(text1.encode())
        f.write(text2.encode())
    print("Updated the reference docs in README.md")


if __name__ == "__main__":
    write_reference_docs()
