import io
import random
import base64

import numpy as np
import PIL.Image
import skimage


def gen_random_id(n=6):
    return "".join(random.choice("abcdefghijklmnopqrtsuvwxyz") for i in range(n))


def img_array_to_uri(img_array, new_size=None):
    img_array = skimage.util.img_as_ubyte(img_array)
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


def get_thumbnail_size_from_shape(shape, base_size):
    base_size = int(base_size)
    img_array = np.zeros(shape, np.uint8)
    img_pil = PIL.Image.fromarray(img_array)
    img_pil.thumbnail((base_size, base_size))
    return img_pil.size
