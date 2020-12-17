from dash_slicer import VolumeSlicer

import numpy as np
from pytest import raises
import dash
import dash_core_components as dcc


def test_slicer_init():
    app = dash.Dash()

    vol = np.random.uniform(0, 255, (100, 100, 100)).astype(np.uint8)

    # Need a valid volume
    with raises(TypeError):
        VolumeSlicer(app, [3, 4, 5])
    with raises(TypeError):
        VolumeSlicer(app, vol[0])

    # Need a valid axis
    with raises(ValueError):
        VolumeSlicer(app, vol, axis=4)

    # Need a valide thumbnail
    with raises(ValueError):
        VolumeSlicer(app, vol, thumbnail=20.2)

    # This works
    s = VolumeSlicer(app, vol)

    # Check properties
    assert isinstance(s.graph, dcc.Graph)
    assert isinstance(s.slider, dcc.Slider)
    assert isinstance(s.stores, list)
    assert all(isinstance(store, (dcc.Store, dcc.Interval)) for store in s.stores)
    for store in [s.clim, s.state, s.extra_traces, s.overlay_data]:
        assert isinstance(store, dcc.Store)


def test_slicer_thumbnail():
    vol = np.random.uniform(0, 255, (100, 100, 100)).astype(np.uint8)

    app = dash.Dash()
    _ = VolumeSlicer(app, vol)
    # Test for name pattern of server-side callback when thumbnails are used
    assert any(["server-data.data" in key for key in app.callback_map])

    app = dash.Dash()
    _ = VolumeSlicer(app, vol, thumbnail=False)
    # No server-side callbacks when no thumbnails are used
    assert not any(["server-data.data" in key for key in app.callback_map])


def test_clim():
    app = dash.Dash()
    vol = np.random.uniform(0, 255, (10, 10, 10)).astype(np.uint8)
    mi, ma = vol.min(), vol.max()

    s = VolumeSlicer(app, vol)
    assert s._initial_clim == (mi, ma)

    s = VolumeSlicer(app, vol, clim=None)
    assert s._initial_clim == (mi, ma)

    s = VolumeSlicer(app, vol, clim=(10, 12))
    assert s._initial_clim == (10, 12)


def test_scene_id_and_context_id():
    app = dash.Dash()

    vol = np.random.uniform(0, 255, (100, 100, 100)).astype(np.uint8)

    s1 = VolumeSlicer(app, vol, axis=0)
    s2 = VolumeSlicer(app, vol, axis=0)
    s3 = VolumeSlicer(app, vol, axis=1)

    # The scene id's are equal, so indicators will match up
    assert s1.scene_id == s2.scene_id and s1.scene_id == s3.scene_id

    # Context id's must be unique
    assert s1._context_id != s2._context_id and s1._context_id != s3._context_id


def test_create_overlay_data():

    app = dash.Dash()
    vol = np.random.uniform(0, 255, (100, 100, 100)).astype(np.uint8)
    s = VolumeSlicer(app, vol)

    # Bool overlay
    overlay = s.create_overlay_data(vol > 10)
    assert isinstance(overlay, list) and len(overlay) == s.nslices
    assert all(isinstance(x, str) for x in overlay)

    # Bool overlay - with color
    overlay = s.create_overlay_data(vol > 10, "#ff0000")
    assert isinstance(overlay, list) and len(overlay) == s.nslices
    assert all(isinstance(x, str) for x in overlay)

    # Uint8 overlay - with colormap
    overlay = s.create_overlay_data(vol.astype(np.uint8), ["#ff0000", "#00ff00"])
    assert isinstance(overlay, list) and len(overlay) == s.nslices
    assert all(isinstance(x, str) for x in overlay)

    # Reset
    overlay = s.create_overlay_data(None)
    assert isinstance(overlay, list) and len(overlay) == s.nslices
    assert all(x is None for x in overlay)

    # Reset by zero mask
    overlay = s.create_overlay_data(vol > 300)
    assert isinstance(overlay, list) and len(overlay) == s.nslices
    assert all(x is None for x in overlay)

    # Wrong
    with raises(TypeError):
        s.create_overlay_data("not a valid mask")
    with raises(ValueError):
        s.create_overlay_data(vol.astype(np.float32))  # wrong dtype
    with raises(ValueError):
        s.create_overlay_data(vol[:-1])  # wrong shape
