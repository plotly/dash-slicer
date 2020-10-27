"""
Dash 3d viewer - a tool to make it easy to build slice-views on 3D image data.
"""


from .slicer import DashVolumeSlicer


__version__ = "0.0.1"
version_info = tuple(map(int, __version__.split(".")))
