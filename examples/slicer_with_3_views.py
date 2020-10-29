"""
An example creating three slice-views through a volume, as is common
in medical applications. In the fourth quadrant we put an isosurface mesh.
"""

import plotly.graph_objects as go
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash_3d_viewer import DashVolumeSlicer
from skimage.measure import marching_cubes
import imageio

app = dash.Dash(__name__)

# Read volumes and create slicer objects
vol = imageio.volread("imageio:stent.npz")
slicer1 = DashVolumeSlicer(app, vol, axis=0, id="slicer1")
slicer2 = DashVolumeSlicer(app, vol, axis=1, id="slicer2")
slicer3 = DashVolumeSlicer(app, vol, axis=2, id="slicer3")

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
        html.Div(
            [html.Center(html.H1("3D")), dcc.Graph(id="graph-helper", figure=fig_mesh)]
        ),
    ],
)


if __name__ == "__main__":
    app.run_server(debug=False)
