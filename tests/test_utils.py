from dash_slicer.utils import (
    img_as_ubyte,
    img_array_to_uri,
    get_thumbnail_size,
    shape3d_to_size2d,
    mask_to_coloured_slices,
)

import numpy as np
from pytest import raises


def test_img_as_ubyte():

    im = np.zeros((100, 100), np.float32)
    im[0, 0] = 100

    # Anything but uint8 is stretched to min-max
    im2 = img_as_ubyte(im)
    assert im2.dtype == np.uint8
    assert im2.min() == 0 and im2.max() == 255

    # Uint- stays where it is
    im2[0, 0] = 100
    im3 = img_as_ubyte(im2)
    assert im3.dtype == np.uint8
    assert im3.min() == 0 and im3.max() == 100


def test_img_array_to_uri():

    im = np.random.uniform(0, 255, (100, 100)).astype(np.uint8)

    r1 = img_array_to_uri(im)
    r2 = img_array_to_uri(im, 32)
    r3 = img_array_to_uri(im, 8)

    for r in (r1, r2, r3):
        assert isinstance(r, str)
        assert r.startswith("data:image/png;base64,")

    assert len(r1) > len(r2) > len(r3)


def test_get_thumbnail_size():

    assert get_thumbnail_size((100, 100), 16) == (16, 16)
    assert get_thumbnail_size((50, 100), 16) == (16, 32)
    assert get_thumbnail_size((100, 100), 8) == (8, 8)
    assert get_thumbnail_size((100, 50), 8) == (16, 8)


def test_shape3d_to_size2d():
    # shape -> z, y, x
    # size -> x, y, out-of-plane
    assert shape3d_to_size2d((12, 13, 14), 0) == (14, 13, 12)
    assert shape3d_to_size2d((12, 13, 14), 1) == (14, 12, 13)
    assert shape3d_to_size2d((12, 13, 14), 2) == (13, 12, 14)

    with raises(IndexError):
        shape3d_to_size2d((12, 13, 14), 3)


def test_mask_to_coloured_slices():
    vol = np.random.uniform(0, 255, (10, 20, 30)).astype(np.uint8)
    mask = vol > 20

    # Check handling of axis
    assert len(mask_to_coloured_slices(mask, 0)) == 10
    assert len(mask_to_coloured_slices(mask, 1)) == 20
    assert len(mask_to_coloured_slices(mask, 2)) == 30

    # Bool overlay
    overlay = mask_to_coloured_slices(mask, 0)
    assert isinstance(overlay, list)
    assert all(isinstance(x, str) for x in overlay)

    # Bool overlay - with color
    overlay = mask_to_coloured_slices(mask, 0, "#ff0000")
    assert isinstance(overlay, list)
    assert all(isinstance(x, str) for x in overlay)

    # Bool overlay - with color rgb
    overlay = mask_to_coloured_slices(mask, 0, [0, 255, 0])
    assert all(isinstance(x, str) for x in overlay)

    # Bool overlay - with color rgba
    overlay = mask_to_coloured_slices(mask, 0, [0, 255, 0, 100])
    assert all(isinstance(x, str) for x in overlay)

    # Uint8 overlay - with colormap
    overlay = mask_to_coloured_slices(vol.astype(np.uint8), 0, ["#ff0000", "#00ff00"])
    assert all(isinstance(x, str) for x in overlay)

    # Reset by zero mask
    overlay = mask_to_coloured_slices(vol > 300, 0)
    assert all(x is None for x in overlay)

    # Wrong
    with raises(ValueError):
        mask_to_coloured_slices(mask, 0, "red")  # named colors not supported yet
    with raises(ValueError):
        mask_to_coloured_slices(mask, 0, [0, 255, 0, 100, 100])  # not a color
    with raises(ValueError):
        mask_to_coloured_slices(mask, 0, [0, 255])  # not a color
    with raises(TypeError):
        mask_to_coloured_slices("not a valid mask", 0)
    with raises(TypeError):
        mask_to_coloured_slices(
            None, 0
        )  # note that the mask in create_overlay_data can be None
    with raises(ValueError):
        mask_to_coloured_slices(vol.astype(np.float32), 0)  # wrong dtype
