"""
An example with two slicers on the same volume.
"""

import dash
import dash_html_components as html
from dash_slicer import VolumeSlicer
import imageio


app = dash.Dash(__name__)
server = app.server

vol = imageio.volread("imageio:stent.npz")
slicer1 = VolumeSlicer(app, vol, axis=1)
slicer2 = VolumeSlicer(app, vol, axis=2)

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
