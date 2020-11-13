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
mi, ma = vol.min(), vol.max()
slicer = VolumeSlicer(app, vol)


slicer.graph.config.update(
    modeBarButtonsToAdd=[
        "drawclosedpath",
        "eraseshape",
    ]
)


# Set colormap so that lower threshold shows in yellow, and higher in red
slicer.set_overlay_colormap([(0, 0, 0, 0), (255, 255, 0, 50), (255, 0, 0, 100)])

app.layout = html.Div(
    [
        slicer.graph,
        slicer.slider,
        dcc.RangeSlider(
            id="level-slider",
            min=vol.min(),
            max=vol.max(),
            step=1,
            value=[mi + 0.1 * (ma - mi), mi + 0.3 * (ma - mi)],
            updatemode="drag",
        ),
        *slicer.stores,
    ]
)


@app.callback(
    Output(slicer.refresh.id, "data"),
    [Input("level-slider", "value")],
)
def handle_slider(level):
    mask = (vol > level[0]).astype("uint8")
    mask += vol > level[1]
    slicer.set_overlay(mask)
    return None


if __name__ == "__main__":
    app.run_server(debug=True)
