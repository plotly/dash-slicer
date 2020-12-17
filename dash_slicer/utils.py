"""
Utilities for the slicer. Implementing these as separete functions keeps
the code in slicer.py smaller, and makes it easier to test.
"""

import io
import base64

import plotly
import numpy as np
import PIL.Image


# The default colors to use for indicators and overlays
discrete_colors = plotly.colors.qualitative.D3


def _thumbnail_size_from_scalar(image_size, ref_size):
    if image_size[0] > image_size[1]:
        return int(ref_size * image_size[0] / image_size[1]), ref_size
    else:
        return ref_size, int(ref_size * image_size[1] / image_size[0])


def img_as_ubyte(img):
    """Quick-n-dirty conversion function.
    We'll have explicit contrast limits eventually.
    """
    if img.dtype == np.uint8:
        return img
    else:
        img = img.astype(np.float32)
        mi, ma = img.min(), img.max()
        img = (img - mi) * (255 / (ma - mi)) + 0.5
        return img.astype(np.uint8)


def img_array_to_uri(img_array, ref_size=None):
    """Convert the given image (numpy array) into a base64-encoded PNG."""
    img_array = img_as_ubyte(img_array)
    img_pil = PIL.Image.fromarray(img_array)
    if ref_size:
        size = img_array.shape[1], img_array.shape[0]
        img_pil.thumbnail(_thumbnail_size_from_scalar(size, ref_size))
    f = io.BytesIO()
    img_pil.save(f, format="PNG")
    base64_str = base64.b64encode(f.getvalue()).decode()
    return "data:image/png;base64," + base64_str


def get_thumbnail_size(size, ref_size):
    """Given an image size (w, h), and a preferred smaller size,
    get the actual size if we let Pillow downscale it.
    """
    # Note that if you call thumbnail() to get the resulting size, then call
    # thumbnail() again with that size, the result may be yet another size.
    img_array = np.zeros(list(reversed(size)), np.uint8)
    img_pil = PIL.Image.fromarray(img_array)
    img_pil.thumbnail(_thumbnail_size_from_scalar(size, ref_size))
    return img_pil.size


def shape3d_to_size2d(shape, axis):
    """Turn a 3d shape (z, y, x) into a local (x', y', z'),
    where z' represents the dimension indicated by axis.
    """
    shape = list(shape)
    axis_value = shape.pop(axis)
    size = list(reversed(shape))
    size.append(axis_value)
    return tuple(size)


def mask_to_coloured_slices(mask, axis, color=None):
    """Turn a mask into a list of base64 encoded coloured slices.
    Set mask to `None` to clear the mask. The color can be a hex color
    or an rgb/rgba tuple. Alternatively, color can be a list of such
    colors, defining a colormap.
    """

    # Check the mask
    if not isinstance(mask, np.ndarray):
        raise TypeError("Mask must be an ndarray or None.")
    elif mask.dtype not in (np.bool, np.uint8):
        raise ValueError(f"Mask must have bool or uint8 dtype, not {mask.dtype}.")

    mask = mask.astype(np.uint8, copy=False)  # need int to index
    nslices = mask.shape[axis]

    # Create a colormap (list) from the given color(s)
    if color is None:
        colormap = discrete_colors[3:]
    elif isinstance(color, str):
        colormap = [color]
    elif isinstance(color, (tuple, list)) and all(
        isinstance(x, (int, float)) for x in color
    ):
        colormap = [color]
    else:
        colormap = list(color)

    # Normalize the colormap so each element is a 4-element tuple
    for i in range(len(colormap)):
        c = colormap[i]
        if isinstance(c, str):
            if c.startswith("#"):
                c = plotly.colors.hex_to_rgb(c)
            else:
                raise ValueError(
                    "Named colors are not (yet) supported, hex colors are."
                )
        c = tuple(int(x) for x in c)
        if len(c) == 3:
            c = c + (100,)
        elif len(c) != 4:
            raise ValueError("Expected color tuples to be 3 or 4 elements.")
        colormap[i] = c

    # Insert zero stub color for where mask is zero
    colormap.insert(0, (0, 0, 0, 0))

    # Produce slices (base64 png strings)
    overlay_slices = []
    for index in range(nslices):
        # Sample the slice
        indices = [slice(None), slice(None), slice(None)]
        indices[axis] = index
        im = mask[tuple(indices)]
        max_mask = im.max()
        if max_mask == 0:
            # If the mask is all zeros, we can simply not draw it
            overlay_slices.append(None)
        else:
            # Turn into rgba
            while len(colormap) <= max_mask:
                colormap.append(colormap[-1])
            colormap_arr = np.array(colormap)
            rgba = colormap_arr[im]
            overlay_slices.append(img_array_to_uri(rgba))

    return overlay_slices
