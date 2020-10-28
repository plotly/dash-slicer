"""
An example creating three slice-views through a volume, as is common
in medical applications. In the fourth quadrant you could place an isosurface mesh.
"""

import dash
import dash_html_components as html
from dash_3d_viewer import DashVolumeSlicer
import imageio


app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer1 = DashVolumeSlicer(app, vol, axis=0, id="slicer1")
slicer2 = DashVolumeSlicer(app, vol, axis=1, id="slicer2")
slicer3 = DashVolumeSlicer(app, vol, axis=2, id="slicer3")


app.layout = html.Div(
    style={
        "display": "grid",
        "grid-template-columns": "40% 40%",
    },
    children=[
        html.Div(
            [
                html.Center(html.H1("Transversal")),
                slicer1.graph,
                html.Br(),
                slicer1.slider,
                *slicer1.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("Coronal")),
                slicer2.graph,
                html.Br(),
                slicer2.slider,
                *slicer2.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("Sagittal")),
                slicer3.graph,
                html.Br(),
                slicer3.slider,
                *slicer3.stores,
            ]
        ),
    ],
)


if __name__ == "__main__":
    app.run_server(debug=False)
