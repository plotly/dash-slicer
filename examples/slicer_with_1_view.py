import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output

import imageio
from dash_3d_viewer import DashVolumeSlicer


app = dash.Dash(__name__)


vol = imageio.volread("imageio:stent.npz")
slicer = DashVolumeSlicer(app, vol)


app.layout = html.Div(
    [html.H6("Blabla"), slicer.graph, html.Br(), slicer.slider, *slicer.stores]
)


# @app.callback(
#     Output('my-output', 'children'),
#     [Input('my-input', 'value')]
# )
# def update_output_div(input_value):
#     return 'Output bla: {}'.format(input_value)


if __name__ == "__main__":
    app.run_server(debug=True)
