"""
A small example showing how to write callbacks involving the slicer's
components. The slicer's components are used as both inputs and outputs.
"""

import dash
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash_slicer import VolumeSlicer
import imageio


app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer = VolumeSlicer(app, vol)

# We can access the components, and modify them
slicer.slider.value = 0

# Define the layour, including extra buttons
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
    Output(slicer.slider.id, "value"),
    [Input("decrease-index", "n_clicks"), Input("increase-index", "n_clicks")],
    [State(slicer.slider.id, "value")],
)
def handle_button_input(press1, press2, index):
    ctx = dash.callback_context
    if ctx.triggered:
        index += 1 if "increase" in ctx.triggered[0]["prop_id"] else -1
    return index


if __name__ == "__main__":
    app.run_server(debug=True)
