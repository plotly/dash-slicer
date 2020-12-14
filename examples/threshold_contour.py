"""
An example demonstrating adding traces.

This shows a volume with a contour overlaid on top. The `extra_traces`
property is used to add scatter traces that represent the contour.
"""

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
from dash_slicer import VolumeSlicer
import imageio
from skimage import measure


app = dash.Dash(__name__, update_title=None)
server = app.server

vol = imageio.volread("imageio:stent.npz")
mi, ma = vol.min(), vol.max()
slicer = VolumeSlicer(app, vol)


app.layout = html.Div(
    [
        slicer.graph,
        slicer.slider,
        dcc.Slider(
            id="level-slider",
            min=mi,
            max=ma,
            step=1,
            value=mi + 0.2 * (ma - mi),
        ),
        *slicer.stores,
    ]
)


@app.callback(
    Output(slicer.extra_traces.id, "data"),
    [Input("level-slider", "value"), Input(slicer.state.id, "data")],
)
def apply_levels(level, state):
    if not state:
        return dash.no_update
    slice = vol[state["index"]]
    contours = measure.find_contours(slice, level)
    traces = []
    for contour in contours:
        traces.append(
            {
                "type": "scatter",
                "mode": "lines",
                "line": {"color": "cyan", "width": 3},
                "x": contour[:, 1],
                "y": contour[:, 0],
            }
        )
    return traces


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
