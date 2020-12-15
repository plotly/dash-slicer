"""
An example creating three slice-views through a volume, as is common
in medical applications. In the fourth quadrant we put an isosurface mesh.
"""

import plotly.graph_objects as go
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash_slicer import VolumeSlicer
from dash.dependencies import Input, Output, State, ALL
from skimage.measure import marching_cubes
import imageio

app = dash.Dash(__name__, update_title=None)
server = app.server

# Read volumes and create slicer objects
vol = imageio.volread("imageio:stent.npz")
slicer0 = VolumeSlicer(app, vol, clim=(0, 800), axis=0)
slicer1 = VolumeSlicer(app, vol, clim=(0, 800), axis=1)
slicer2 = VolumeSlicer(app, vol, clim=(0, 800), axis=2)

# Calculate isosurface and create a figure with a mesh object
verts, faces, _, _ = marching_cubes(vol, 300, step_size=4)
x, y, z = verts.T
i, j, k = faces.T
mesh = go.Mesh3d(x=z, y=y, z=x, opacity=0.2, i=k, j=j, k=i)
fig = go.Figure(data=[mesh])
fig.update_layout(uirevision="anything")  # prevent orientation reset on update


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
                slicer0.graph,
                html.Br(),
                slicer0.slider,
                *slicer0.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("Coronal")),
                slicer1.graph,
                html.Br(),
                slicer1.slider,
                *slicer1.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("Sagittal")),
                slicer2.graph,
                html.Br(),
                slicer2.slider,
                *slicer2.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("3D")),
                dcc.Graph(id="3Dgraph", figure=fig),
            ]
        ),
    ],
)


# Callback to display slicer view positions in the 3D view
app.clientside_callback(
    """
function update_3d_figure(states, ori_figure) {
    let traces = [ori_figure.data[0]]
    for (let state of states) {
        if (!state) continue;
        let xrange = state.xrange;
        let yrange = state.yrange;
        let xyz = [
            [xrange[0], xrange[1], xrange[1], xrange[0], xrange[0]],
            [yrange[0], yrange[0], yrange[1], yrange[1], yrange[0]],
            [state.zpos, state.zpos, state.zpos, state.zpos, state.zpos]
        ];
        xyz.splice(2 - state.axis, 0, xyz.pop());
        let s = {
            type: 'scatter3d',
            x: xyz[0], y: xyz[1], z: xyz[2],
            mode: 'lines', line: {color: state.color}
        };
        traces.push(s);
    }
    let figure = {...ori_figure};
    figure.data = traces;
    return figure;
}
    """,
    Output("3Dgraph", "figure"),
    [Input({"scene": slicer0.scene_id, "context": ALL, "name": "state"}, "data")],
    [State("3Dgraph", "figure")],
)


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
