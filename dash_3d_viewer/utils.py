import random

import PIL.Image
import skimage
from plotly.utils import ImageUriValidator


def gen_random_id(n=6):
    return "".join(random.choice("abcdefghijklmnopqrtsuvwxyz") for i in range(n))


def img_array_to_uri(img_array):
    img_array = skimage.util.img_as_ubyte(img_array)
    img_pil = PIL.Image.fromarray(img_array)
    uri = ImageUriValidator.pil_image_to_uri(img_pil)
    return uri
