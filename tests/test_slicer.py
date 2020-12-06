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
