"""
An example demonstrating overlays, by showing a mask obtained by thresholding on top.
"""

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
from dash_slicer import VolumeSlicer
import imageio


app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer = VolumeSlicer(app, vol)

devnull = dcc.Store(id="devnull", data=0)

app.layout = html.Div(
    [
        slicer.graph,
        slicer.slider,
        dcc.Slider(
            id="level-slider",
            min=vol.min(),
            max=vol.max(),
            step=1,
            value=0.5 * (vol.max() + vol.min()),
            updatemode="drag",
        ),
        *slicer.stores,
    ]
)


@app.callback(
    Output(slicer.trigger.id, "data"),
    [Input("level-slider", "value")],
)
def handle_slider(level):
    slicer.set_overlay(vol > level)
    return None


if __name__ == "__main__":
    app.run_server(debug=True)
