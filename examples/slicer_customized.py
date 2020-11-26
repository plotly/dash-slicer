"""
An example showing how to customize the slicer and write callbacks
involving the slicer's components.
"""

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
from dash_slicer import VolumeSlicer
import imageio


app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer = VolumeSlicer(app, vol)


# We can access the components, and modify them
slicer.slider.value = 10

# The graph can be configured
slicer.graph.config.update({"modeBarButtonsToAdd": ["drawclosedpath", "eraseshape"]})

# The plotly figure can be accessed too
slicer.graph.figure.update_layout(margin=dict(l=0, r=0, b=30, t=0, pad=4))
slicer.graph.figure.update_xaxes(showgrid=True, showticklabels=True)
slicer.graph.figure.update_yaxes(showgrid=True, showticklabels=True)

setpos_store = dcc.Store(
    id={"context": "app", "scene": slicer.scene_id, "name": "setpos"}
)


# Define the layout, including extra buttons
app.layout = html.Div(
    [
        slicer.graph,
        html.Br(),
        html.Div(
            style={"display": "flex"},
            children=[
                html.Div("", id="index-show", style={"padding": "0.4em"}),
                html.Button("<", id="decrease-index"),
                html.Div(slicer.slider, style={"flexGrow": "1"}),
                html.Button(">", id="increase-index"),
            ],
        ),
        setpos_store,
        *slicer.stores,
    ]
)

# New callbacks for our added widgets


@app.callback(
    Output("index-show", "children"),
    [Input(slicer.slider.id, "value")],
)
def show_slider_value(index):
    return str(index)


@app.callback(
    Output(setpos_store.id, "data"),
    [Input("decrease-index", "n_clicks"), Input("increase-index", "n_clicks")],
    [State(slicer.slider.id, "value")],
)
def handle_button_input(press1, press2, index):
    ctx = dash.callback_context
    if ctx.triggered:
        index += 1 if "increase" in ctx.triggered[0]["prop_id"] else -1
    return None, None, index  # xyz in scene coords


if __name__ == "__main__":
    # Note: dev_tools_props_check negatively affects the performance of VolumeSlicer
    app.run_server(debug=True, dev_tools_props_check=False)
