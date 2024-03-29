"""
dash_slicer - a volume slicer for Dash
"""

from .slicer import VolumeSlicer  # noqa: F401


__version__ = "0.3.1"
version_info = tuple(map(int, __version__.split(".")))
