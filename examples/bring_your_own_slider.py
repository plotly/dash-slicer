"""
Bring your own slider ... or dropdown. This example shows how to use a
different input element for the slice position. A store is created with
certain predefined elements. The value set to this store is an xyz
position in scene coordinates. None can be used to ignore certain
dimensions. The slider element itself is hidden.
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

setpos_store = dcc.Store(
    id={"context": "app", "scene": slicer.scene_id, "name": "setpos"}
)

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
        setpos_store,
        *slicer.stores,
    ]
)


@app.callback(
    Output(setpos_store.id, "data"),
    [Input(dropdown.id, "value")],
)
def handle_dropdown_input(index):
    return None, None, index  # xyz in scene coords


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
