from dash_slicer.utils import shape3d_to_size2d

from pytest import raises


def test_shape3d_to_size2d():
    # shape -> z, y, x
    # size -> x, y, out-of-plane
    assert shape3d_to_size2d((12, 13, 14), 0) == (14, 13, 12)
    assert shape3d_to_size2d((12, 13, 14), 1) == (14, 12, 13)
    assert shape3d_to_size2d((12, 13, 14), 2) == (13, 12, 14)

    with raises(IndexError):
        shape3d_to_size2d((12, 13, 14), 3)
