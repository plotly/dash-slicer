"""
An simple example that demonstrates how the slicer's index can be both read and written.

See set_slicer_position_interactively.py for a more advanced / realistic example.
"""

import dash
import dash_html_components as html
from dash_slicer import VolumeSlicer
import dash_core_components as dcc
from dash.dependencies import Input, Output, ALL
import imageio


app = dash.Dash(__name__)  # , update_title=None)

vol = imageio.volread("imageio:stent.npz")
slicer = VolumeSlicer(app, vol)

# We create a slider as an element that gets set from the slicer's state
# and is also used to set the slicer's position. But this element can be anything,
slider = dcc.Slider(id="slider", max=slicer.nslices)

# Create a store with a specific ID so we can set the slicer position.
setpos_store = dcc.Store(
    id={"context": "app", "scene": slicer.scene_id, "name": "setpos"}
)

app.layout = html.Div(
    [slicer.graph, slicer.slider, slider, setpos_store, *slicer.stores]
)


# Add callback to listen to changes in state of any slicers with a matching scene_id.
# Note that we could also use a simpler callback using slicer.state as input.
@app.callback(
    Output("slider", "value"),
    Input({"scene": slicer.scene_id, "context": ALL, "name": "state"}, "data"),
)
def respond_to_slicer_state(states):
    for state in states:
        if state and state["axis"] == 0:
            return state["index"]
    return dash.no_update


# Add a callback to set the slicer position.
@app.callback(
    Output(setpos_store.id, "data"),
    Input("slider", "value"),
)
def set_position_of_all_slicers_with_scene_id(value):
    return None, None, value  # x, y, z (in scene coordinates)


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
