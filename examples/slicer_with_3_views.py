"""
An example creating three slice-views through a volume, as is common
in medical applications. In the fourth quadrant we put an isosurface mesh.
"""

import plotly.graph_objects as go
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash_slicer import VolumeSlicer
from skimage.measure import marching_cubes
import imageio

app = dash.Dash(__name__)
server = app.server

# Read volumes and create slicer objects
vol = imageio.volread("imageio:stent.npz")
slicer1 = VolumeSlicer(app, vol, reverse_y=False, axis=0)
slicer2 = VolumeSlicer(app, vol, reverse_y=False, axis=1)
slicer3 = VolumeSlicer(app, vol, reverse_y=False, axis=2)

# Calculate isosurface and create a figure with a mesh object
verts, faces, _, _ = marching_cubes(vol, 300, step_size=2)
x, y, z = verts.T
i, j, k = faces.T
fig_mesh = go.Figure()
fig_mesh.add_trace(go.Mesh3d(x=z, y=y, z=x, opacity=0.2, i=k, j=j, k=i))

# Put everything together in a 2x2 grid
app.layout = html.Div(
    style={
        "display": "grid",
        "gridTemplateColumns": "40% 40%",
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
        html.Div(
            [html.Center(html.H1("3D")), dcc.Graph(id="graph-helper", figure=fig_mesh)]
        ),
    ],
)


if __name__ == "__main__":
    # Note that debug mode negatively affects the performance of VolumeSlicer
    app.run_server(debug=False)
