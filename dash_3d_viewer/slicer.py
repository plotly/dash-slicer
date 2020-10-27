import numpy as np
from plotly.graph_objects import Figure
from dash import Dash
from dash.dependencies import Input, Output, State
from dash_core_components import Graph, Slider, Store

from .utils import img_array_to_uri


class DashVolumeSlicer:
    """A slicer to show 3D image data in Dash."""

    def __init__(self, app, volume, axis=0):

        assert isinstance(app, Dash)
        if not (isinstance(volume, np.ndarray) and volume.ndim == 3):
            raise TypeError("DashVolumeSlicer expects a 3D numpy array")

        self._id = "thereisonlyoneslicerfornow"
        self._volume = volume
        self._axis = int(axis)
        self._max_slice = self._volume.shape[self._axis]
        assert 0 <= self._axis <= 2

        slice_shape = list(volume.shape)
        slice_shape.pop(self._axis)

        # Create the figure object
        fig = Figure()
        fig.update_layout(template=None)
        fig.update_xaxes(showgrid=False, showticklabels=False, zeroline=False)
        fig.update_yaxes(
            showgrid=False, scaleanchor="x", showticklabels=False, zeroline=False
        )
        # Add an empty layout image that we can populate from JS.
        fig.add_layout_image(
            dict(
                source="",
                xref="x",
                yref="y",
                x=0,
                y=0,
                sizex=slice_shape[0],
                sizey=slice_shape[1],
                sizing="contain",
                layer="below",
            )
        )
        fig.update_xaxes(
            showgrid=False,
            range=(0, slice_shape[0]),
            showticklabels=False,
            zeroline=False,
        )
        fig.update_yaxes(
            showgrid=False,
            scaleanchor="x",
            range=(slice_shape[1], 0),
            showticklabels=False,
            zeroline=False,
        )
        fig.update_layout(
            {
                "margin": dict(l=0, r=0, b=0, t=0, pad=4),
            }
        )

        self.graph = Graph(
            id="graph",
            figure=fig,
            config={"scrollZoom": True},
        )

        self.slider = Slider(
            id="slider",
            min=0,
            max=self._max_slice - 1,
            step=1,
            value=self._max_slice // 2,
            updatemode="drag",
        )

        self.stores = [
            Store(id="slice-index", data=volume.shape[self._axis] // 2),
            Store(id="_requested-slice-index", data=0),
            Store(id="_slice-data", data=""),
        ]

        self._create_server_handlers(app)
        self._create_client_handlers(app)

    def _slice(self, index):
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        return self._volume[tuple(indices)]

    def _create_server_handlers(self, app):
        @app.callback(
            Output("_slice-data", "data"),
            [Input("_requested-slice-index", "data")],
        )
        def upload_requested_slice(slice_index):
            slice = self._slice(slice_index)
            slice = (slice.astype(np.float32) * (255 / slice.max())).astype(np.uint8)
            return [slice_index, img_array_to_uri(slice)]

    def _create_client_handlers(self, app):

        app.clientside_callback(
            """
        function handle_slider_move(index) {
            return index;
        }
        """,
            Output("slice-index", "data"),
            [Input("slider", "value")],
        )

        app.clientside_callback(
            """
        function handle_slice_index(index) {
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            if (slice_cache[index]) {
                return window.dash_clientside.no_update;
            } else {
                console.log('requesting slice ' + index)
                return index;
            }
        }
        """.replace(
                "{{ID}}", self._id
            ),
            Output("_requested-slice-index", "data"),
            [Input("slice-index", "data")],
        )

        # app.clientside_callback("""
        # function update_slider_pos(index) {
        #     return index;
        # }
        # """,
        #     [Output("slice-index", "data")],
        #     [State("slider", "value")],
        # )

        app.clientside_callback(
            """
        function handle_incoming_slice(index, index_and_data, ori_figure) {
            let new_index = index_and_data[0];
            let new_data = index_and_data[1];
            // Store data in cache
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            slice_cache[new_index] = new_data;
            // Get the data we need *now*
            let data = slice_cache[index];
            // Maybe we do not need an update
            if (!data) {
                return window.dash_clientside.no_update;
            }
            if (data == ori_figure.layout.images[0].source) {
                return window.dash_clientside.no_update;
            }
            // Otherwise, perform update
            console.log("updating figure");
            let figure = {...ori_figure};
            figure.layout.images[0].source = data;
            return figure;
        }
        """.replace(
                "{{ID}}", self._id
            ),
            Output("graph", "figure"),
            [Input("slice-index", "data"), Input("_slice-data", "data")],
            [State("graph", "figure")],
        )
