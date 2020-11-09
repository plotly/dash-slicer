"""
An example with two slicers at the same axis, and one on another axis.
This demonstrates how multiple indicators can be shown per axis.

Sharing the same scene_id is enough for the slicers to show each-others
position. If the same volume object would be given, it works by default,
because the default scene_id is a hash of the volume object. Specifying
a scene_id provides slice position indicators even when slicing through
different volumes.

Further, this example has one slider showing data with different spacing.
Note how the indicators represent the actual position in "scene coordinates".

"""

import dash
import dash_html_components as html
from dash_slicer import VolumeSlicer
import imageio


app = dash.Dash(__name__)

vol1 = imageio.volread("imageio:stent.npz")

vol2 = vol1[::3, ::2, :]
spacing = 3, 2, 1
ori = 110, 120, 140


slicer1 = VolumeSlicer(
    app, vol1, axis=1, origin=ori, reverse_y=False, scene_id="scene1"
)
slicer2 = VolumeSlicer(
    app, vol1, axis=0, origin=ori, reverse_y=False, scene_id="scene1"
)
slicer3 = VolumeSlicer(
    app, vol2, axis=0, origin=ori, spacing=spacing, reverse_y=False, scene_id="scene1"
)

app.layout = html.Div(
    style={
        "display": "grid",
        "gridTemplateColumns": "40% 40%",
    },
    children=[
        html.Div(
            [
                html.H1("Coronal"),
                slicer1.graph,
                slicer1.slider,
                *slicer1.stores,
            ]
        ),
        html.Div(
            [
                html.H1("Transversal 1"),
                slicer2.graph,
                slicer2.slider,
                *slicer2.stores,
            ]
        ),
        html.Div(),
        html.Div(
            [
                html.H1("Transversal 2"),
                slicer3.graph,
                slicer3.slider,
                *slicer3.stores,
            ]
        ),
    ],
)


if __name__ == "__main__":
    app.run_server(debug=True)