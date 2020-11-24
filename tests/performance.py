"""
A test application to test the performance of a few methods to display an image.
"""

import plotly.graph_objects as go
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
import imageio
from dash_slicer.utils import img_array_to_uri


app = dash.Dash(__name__)
server = app.server

# Read volumes and create slicer objects
vol = imageio.volread("imageio:stent.npz")

slices_png = [img_array_to_uri(im) for im in vol]

OPTIONS = ["noop", "empty", "heatmap", "heatmapgl", "png", "png not reversed"]

##


fig = go.Figure(data=[])
fig.update_layout(
    template=None,
    margin={"l": 0, "r": 0, "b": 0, "t": 0, "pad": 4},
    dragmode="pan",  # user navigates by panning
)
fig.update_xaxes(
    showgrid=False,
    showticklabels=False,
    zeroline=False,
)
fig.update_yaxes(
    showgrid=False,
    scaleanchor="x",
    showticklabels=False,
    zeroline=False,
    range=[0, 128],
)


app.layout = html.Div(
    children=[
        dcc.Dropdown(
            id="dropdown",
            options=[{"label": name, "value": name} for name in OPTIONS],
            value="noop",
        ),
        html.Div(id="fps"),
        html.Br(),
        dcc.Graph(id="graph", figure=fig),
        dcc.Interval(id="interval", interval=1),
        dcc.Store(id="index", data=0),
        dcc.Store(id="data_list", data=vol),
        dcc.Store(id="data_png", data=slices_png),
    ]
)

##


app.clientside_callback(
    """
function update_index(_, index) {
    index += 1;
    if (index > 200) index = 50;
    return index;
}
""",
    Output("index", "data"),
    [Input("interval", "n_intervals")],
    [
        State("index", "data"),
    ],
)


app.clientside_callback(
    """
function update_figure(index, option, ori_figure, data_list, data_png) {

    // Get FPS
    let fps_result = dash_clientside.no_update;
    let now = performance.now();
    let etime = now - (window.lasttime || 0);
    if (etime > 1000) {
        let nframes = (window.framecount || 0) + 1;
        fps_result = Math.round(nframes * 1000 / etime) + " FPS";
        window.lasttime = now;
        window.framecount = 0;
    } else {
        window.framecount += 1;
    }

    // Get figure
    let figure_result = dash_clientside.no_update;

    if (!option || option == 'noop') {
        // noop
    } else if (option == 'sleep') {
        while (performance.now() < now + 500) {}
    } else if (option == 'empty') {
        figure_result = {...ori_figure};
        figure_result.layout.yaxis.range = [128, 0];
        figure_result.data = [];
    } else if (option == 'heatmap') {
        let trace = {type: 'heatmap', z: data_list[index]};
        figure_result = {...ori_figure};
        figure_result.layout.yaxis.range = [128, 0];
        figure_result.data = [trace];
    } else if (option == 'heatmapgl') {
        let trace = {type: 'heatmapgl', z: data_list[index]};
        figure_result = {...ori_figure};
        figure_result.layout.yaxis.range = [128, 0];
        figure_result.data = [trace];
    } else if (option == 'png') {
        let trace = {type: 'image', source: data_png[index]};
        figure_result = {...ori_figure};
        figure_result.layout.yaxis.range = [128, 0];
        figure_result.data = [trace];
    } else if (option == 'png not reversed') {
        let trace = {type: 'image', source: data_png[index]};
        figure_result = {...ori_figure};
        figure_result.layout.yaxis.range = [0, 128];
        figure_result.data = [trace];
    } else {
        fps_result = "invalid option: " + option;
    }
    return [figure_result, fps_result];
}
""",
    [Output("graph", "figure"), Output("fps", "children")],
    [Input("index", "data")],
    [
        State("dropdown", "value"),
        State("graph", "figure"),
        State("data_list", "data"),
        State("data_png", "data"),
    ],
)


if __name__ == "__main__":
    app.run_server(debug=True)
