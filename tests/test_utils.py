from dash_slicer.utils import img_array_to_uri, get_thumbnail_size, shape3d_to_size2d

import numpy as np
from pytest import raises


def test_img_array_to_uri():

    im = np.random.uniform(0, 255, (100, 100)).astype(np.uint8)

    r1 = img_array_to_uri(im)
    r2 = img_array_to_uri(im, (32, 32))
    r3 = img_array_to_uri(im, (8, 8))

    for r in (r1, r2, r3):
        assert isinstance(r, str)
        assert r.startswith("data:image/png;base64,")

    assert len(r1) > len(r2) > len(r3)


def test_get_thumbnail_size():

    assert get_thumbnail_size((100, 100), (16, 16)) == (16, 16)
    assert get_thumbnail_size((50, 100), (16, 16)) == (8, 16)
    assert get_thumbnail_size((100, 100), (8, 16)) == (8, 8)


def test_shape3d_to_size2d():
    # shape -> z, y, x
    # size -> x, y, out-of-plane
    assert shape3d_to_size2d((12, 13, 14), 0) == (14, 13, 12)
    assert shape3d_to_size2d((12, 13, 14), 1) == (14, 12, 13)
    assert shape3d_to_size2d((12, 13, 14), 2) == (13, 12, 14)

    with raises(IndexError):
        shape3d_to_size2d((12, 13, 14), 3)
