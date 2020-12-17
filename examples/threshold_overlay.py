"""
An example demonstrating overlays.

This shows a volume with a mask overlay. In this case the mask has 3
possible values (0, 1, 2), and is created by applying two thresholds
to the image data.
"""

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
from dash_slicer import VolumeSlicer
import numpy as np
import imageio


app = dash.Dash(__name__, update_title=None)
server = app.server

vol = imageio.volread("imageio:stent.npz")
mi, ma = vol.min(), vol.max()
slicer = VolumeSlicer(app, vol, clim=(0, 800))


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
        ),
        *slicer.stores,
    ]
)


# Define colormap to make the lower threshold shown in yellow, and higher in red
colormap = [(255, 255, 0, 50), (255, 0, 0, 100)]


@app.callback(
    Output(slicer.overlay_data.id, "data"),
    [Input("level-slider", "value")],
)
def apply_levels(level):
    mask = np.zeros(vol.shape, np.uint8)
    mask += vol > level[0]
    mask += vol > level[1]
    return slicer.create_overlay_data(mask, colormap)


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
