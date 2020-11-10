"""
Bring your own slider ... or dropdown. This example shows how to use a
different input element for the slice index. The slider's value is used
as an output, but the slider element itself is hidden.
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

dropdown = dcc.Dropdown(
    id="dropdown",
    options=[{"label": f"slice {i}", "value": i} for i in range(0, vol.shape[0], 10)],
    value=50,
)


# Define the layout
app.layout = html.Div(
    [
        slicer.graph,
        dropdown,
        html.Div(slicer.slider, style={"display": "none"}),
        *slicer.stores,
    ]
)


@app.callback(
    Output(slicer.slider.id, "value"),
    [Input(dropdown.id, "value")],
)
def handle_dropdown_input(index):
    return index


if __name__ == "__main__":
    app.run_server(debug=True)
