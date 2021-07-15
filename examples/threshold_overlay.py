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

import plotly.express as px

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
COLORMAP = px.colors.sequential.Turbo
# If the px color map uses RBG values, then enable this to convert to series of ints
# for i, c in enumerate(COLORMAP):
#     COLORMAP[i] = c.strip("rgb(").strip(')').split(',')

@app.callback(
    Output(slicer.overlay_data.id, "data"),
    [Input("level-slider", "value")],
)
def apply_levels(level):
    n_bins = len(COLORMAP)
    mask = np.zeros(vol.shape, np.uint8)
    data_range = vol.max() - vol.min()
    thresholds = [ vol.min() + i * data_range / n_bins for i in range(1,n_bins + 1) ]

    for i in range(n_bins):
        mask += vol < thresholds[i]
    return slicer.create_overlay_data(mask, COLORMAP)


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
