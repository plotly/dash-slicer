import PIL.Image
import skimage
from plotly.utils import ImageUriValidator


def img_array_to_uri(img_array):
    img_array = skimage.util.img_as_ubyte(img_array)
    img_pil = PIL.Image.fromarray(img_array)
    uri = ImageUriValidator.pil_image_to_uri(img_pil)
    return uri
