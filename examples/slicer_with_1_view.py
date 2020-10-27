"""
A truly minimal example.
"""

import dash
import dash_html_components as html
from dash_3d_viewer import DashVolumeSlicer
import imageio


app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer = DashVolumeSlicer(app, vol)

app.layout = html.Div([slicer.graph, slicer.slider, *slicer.stores])


if __name__ == "__main__":
    app.run_server(debug=True)
