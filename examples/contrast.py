"""
A small example demonstrating contrast limits.
"""

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
from dash_slicer import VolumeSlicer
import imageio


app = dash.Dash(__name__, update_title=None)

vol = imageio.volread("imageio:stent.npz")
slicer = VolumeSlicer(app, vol, clim=(0, 1000))
clim_slider = dcc.RangeSlider(
    id="clim-slider", min=vol.min(), max=vol.max(), value=(0, 1000)
)

app.layout = html.Div([slicer.graph, slicer.slider, clim_slider, *slicer.stores])


@app.callback(Output(slicer.clim.id, "data"), [Input("clim-slider", "value")])
def update_clim(value):
    return value


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
