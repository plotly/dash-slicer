"""
An example demonstrating overlays.

This shows a volume with a mask overlaid. In this case the mask has 3
possible values (0, 1, 2), and is created by applying two thresholds
to the image data.
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

# Set colormap so that lower threshold shows in yellow, and higher in red
slicer.set_overlay_colormap([(0, 0, 0, 0), (255, 255, 0, 50), (255, 0, 0, 100)])

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
    mask = (vol > level).astype("uint8")
    mask += vol > level / 2
    slicer.set_overlay(mask)
    return None


if __name__ == "__main__":
    app.run_server(debug=True)
