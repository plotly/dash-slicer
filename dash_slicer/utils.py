import io
import base64

import numpy as np
import PIL.Image


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


def img_array_to_uri(img_array, new_size=None):
    """Convert the given image (numpy array) into a base64-encoded PNG."""
    img_array = img_as_ubyte(img_array)
    # todo: leverage this Plotly util once it becomes part of the public API (also drops the Pillow dependency)
    # from plotly.express._imshow import _array_to_b64str
    # return _array_to_b64str(img_array)
    img_pil = PIL.Image.fromarray(img_array)
    if new_size:
        img_pil.thumbnail(new_size)
    # The below was taken from plotly.utils.ImageUriValidator.pil_image_to_uri()
    f = io.BytesIO()
    img_pil.save(f, format="PNG")
    base64_str = base64.b64encode(f.getvalue()).decode()
    return "data:image/png;base64," + base64_str


def get_thumbnail_size(size, new_size):
    """Given an image size (w, h), and a preferred smaller size,
    get the actual size if we let Pillow downscale it.
    """
    img_array = np.zeros(list(reversed(size)), np.uint8)
    img_pil = PIL.Image.fromarray(img_array)
    img_pil.thumbnail(new_size)
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
