"""
An example with two slicers on the same volume.
"""

import dash
import dash_html_components as html
from dash_3d_viewer import DashVolumeSlicer
import imageio


app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer1 = DashVolumeSlicer(app, vol, axis=1, id="slicer1")
slicer2 = DashVolumeSlicer(app, vol, axis=2, id="slicer2")

app.layout = html.Div(
    style={
        "display": "grid",
        "grid-template-columns": "40% 40%",
    },
    children=[
        html.Div(
            [
                html.H1("Coronal"),
                slicer1.graph,
                html.Br(),
                slicer1.slider,
                *slicer1.stores,
            ]
        ),
        html.Div(
            [
                html.H1("Sagittal"),
                slicer2.graph,
                html.Br(),
                slicer2.slider,
                *slicer2.stores,
            ]
        ),
    ],
)


if __name__ == "__main__":
    app.run_server(debug=True)
