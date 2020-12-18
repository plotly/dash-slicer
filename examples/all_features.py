"""
An example that is (tries to be) a demo of all features.
"""

import plotly.graph_objects as go
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash_slicer import VolumeSlicer
from dash.dependencies import Input, Output, State, ALL
import imageio
from skimage import measure


app = dash.Dash(__name__, update_title=None)
server = app.server

# Read volume
vol = imageio.volread("imageio:stent.npz")
vol = vol[::3, :, :]
spacing = 3, 1, 1
ori = 1000, 2000, 3000

# Create slicer objects
slicer0 = VolumeSlicer(app, vol, spacing=spacing, origin=ori, axis=0, thumbnail=False)
slicer1 = VolumeSlicer(
    app, vol, spacing=spacing, origin=ori, axis=1, thumbnail=8, reverse_y=False
)
slicer2 = VolumeSlicer(app, vol, spacing=spacing, origin=ori, axis=2, color="#00ff99")

# Put everything together in a 2x2 grid
app.layout = html.Div(
    style={
        "display": "grid",
        "gridTemplateColumns": "33% 33% 33%",
    },
    children=[
        html.Div(
            [
                html.Center(html.H1("Axis 0")),
                slicer0.graph,
                html.Br(),
                slicer0.slider,
                *slicer0.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("Axis 1")),
                slicer1.graph,
                html.Br(),
                slicer1.slider,
                *slicer1.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("Axis 2")),
                slicer2.graph,
                html.Br(),
                slicer2.slider,
                *slicer2.stores,
            ]
        ),
        html.Div(
            [
                html.Center(html.H1("3D")),
                dcc.Graph(id="3Dgraph", figure=go.Figure()),
            ]
        ),
        html.Div(
            [
                html.Div("Threshold level"),
                dcc.Slider(id="level", max=2000, value=500),
                html.Div("Contrast limits"),
                dcc.RangeSlider(id="clim", max=2000, value=(0, 800)),
            ]
        ),
        dcc.Markdown(
            """
            Take note of:

            Axis 0:
            * Full-res thumbnails.

            Axis 1:
            * Very low-res thumbnails.
            * Elongated voxels.
            * The `reverse_y` is false.
            * Yellow overlay based on threshold.

            Axis 2:
            * Default low-res thumbnails.
            * Elongated voxels.
            * Yellow contour based on threshold..
            * A custom brighter green indicator.

            3D view:
            * An origin in the thousands.

            """
        ),
    ],
)


# Callback to display slicer view positions in the 3D view
app.clientside_callback(
    """
function update_3d_figure(states, ori_figure) {
    let traces = [];
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
            mode: 'lines', line: {color: state.color},
            hoverinfo: 'skip',
            showlegend: false,
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


# Callback to add overlay in axis 1
@app.callback(
    Output(slicer1.overlay_data.id, "data"),
    [Input("level", "value")],
)
def update_overlay(level):
    return slicer1.create_overlay_data(vol > level, "#ffff00")


# Callback to add contours in axes 2
@app.callback(
    Output(slicer2.extra_traces.id, "data"),
    [Input(slicer2.state.id, "data"), Input("level", "value")],
)
def update_contour(state, level):
    if not state:
        return dash.no_update
    slice = vol[:, :, state["index"]]
    contours = measure.find_contours(slice, level)
    traces = []
    for contour in contours:
        traces.append(
            {
                "type": "scatter",
                "mode": "lines",
                "line": {"color": "yellow", "width": 3},
                "x": contour[:, 1] * spacing[1] + ori[1],
                "y": contour[:, 0] * spacing[0] + ori[0],
                "hoverinfo": "skip",
                "showlegend": False,
            }
        )
    return traces


# Callback to set contrast limits
@app.callback(
    [
        Output(slicer0.clim.id, "data"),
        Output(slicer1.clim.id, "data"),
        Output(slicer2.clim.id, "data"),
    ],
    [Input("clim", "value")],
)
def update_clim(clim):
    return [clim, clim, clim]


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
