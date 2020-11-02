import numpy as np
from plotly.graph_objects import Figure, Image
from dash import Dash
from dash.dependencies import Input, Output, State
from dash_core_components import Graph, Slider, Store

from .utils import gen_random_id, img_array_to_uri


empty_img_str = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg=="


class DashVolumeSlicer:
    """A slicer to show 3D image data in Dash."""

    def __init__(self, app, volume, axis=0, id=None):
        if not isinstance(app, Dash):
            raise TypeError("Expect first arg to be a Dash app.")
        # Check and store volume
        if not (isinstance(volume, np.ndarray) and volume.ndim == 3):
            raise TypeError("Expected volume to be a 3D numpy array")
        self._volume = volume
        # Check and store axis
        if not (isinstance(axis, int) and 0 <= axis <= 2):
            raise ValueError("The given axis must be 0, 1, or 2.")
        self._axis = int(axis)
        # Check and store id
        if id is None:
            id = gen_random_id()
        elif not isinstance(id, str):
            raise TypeError("Id must be a string")
        self._id = id

        # Get the slice size (width, height), and max index
        arr_shape = list(volume.shape)
        arr_shape.pop(self._axis)
        slice_size = list(reversed(arr_shape))
        self._max_index = self._volume.shape[self._axis] - 1

        # Prep low-res slices
        thumbnails = [
            img_array_to_uri(self._slice(i), (32, 32))
            for i in range(self._max_index + 1)
        ]

        # Create a placeholder trace
        # todo: can add "%{z[0]}", but that would be the scaled value ...
        trace = Image(source=empty_img_str, hovertemplate="(%{x}, %{y})<extra></extra>")
        # Create the figure object
        fig = Figure(data=[trace])
        fig.update_layout(
            template=None,
            margin=dict(l=0, r=0, b=0, t=0, pad=4),
        )
        fig.update_xaxes(
            showgrid=False,
            # range=(0, slice_size[0]),
            showticklabels=False,
            zeroline=False,
        )
        fig.update_yaxes(
            showgrid=False,
            scaleanchor="x",
            # range=(slice_size[1], 0),  # todo: allow flipping x or y
            showticklabels=False,
            zeroline=False,
        )
        # Wrap the figure in a graph
        # todo: or should the user provide this?
        self.graph = Graph(
            id=self._subid("graph"),
            figure=fig,
            config={"scrollZoom": True},
        )
        # Create a slider object that the user can put in the layout (or not)
        self.slider = Slider(
            id=self._subid("slider"),
            min=0,
            max=self._max_index,
            step=1,
            value=self._max_index // 2,
            updatemode="drag",
        )
        # Create the stores that we need (these must be present in the layout)
        self.stores = [
            Store(id=self._subid("slice-index"), data=volume.shape[self._axis] // 2),
            Store(id=self._subid("_requested-slice-index"), data=0),
            Store(id=self._subid("_slice-data"), data=""),
            Store(id=self._subid("_slice-data-lowres"), data=thumbnails),
        ]

        self._create_server_callbacks(app)
        self._create_client_callbacks(app)

    def _subid(self, subid):
        """Given a subid, get the full id including the slicer's prefix."""
        return self._id + "-" + subid

    def _slice(self, index):
        """Sample a slice from the volume."""
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        im = self._volume[tuple(indices)]
        return (im.astype(np.float32) * (255 / im.max())).astype(np.uint8)

    def _create_server_callbacks(self, app):
        """Create the callbacks that run server-side."""

        @app.callback(
            Output(self._subid("_slice-data"), "data"),
            [Input(self._subid("_requested-slice-index"), "data")],
        )
        def upload_requested_slice(slice_index):
            slice = self._slice(slice_index)
            return [slice_index, img_array_to_uri(slice)]

    def _create_client_callbacks(self, app):
        """Create the callbacks that run client-side."""

        app.clientside_callback(
            """
        function handle_slider_move(index) {
            return index;
        }
        """,
            Output(self._subid("slice-index"), "data"),
            [Input(self._subid("slider"), "value")],
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
            Output(self._subid("_requested-slice-index"), "data"),
            [Input(self._subid("slice-index"), "data")],
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
        function handle_incoming_slice(index, index_and_data, ori_figure, lowres) {
            let new_index = index_and_data[0];
            let new_data = index_and_data[1];
            // Store data in cache
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            slice_cache[new_index] = new_data;
            // Get the data we need *now*
            let data = slice_cache[index];
            //slice_cache[new_index] = undefined;  // todo: disabled cache for now!
            // Maybe we do not need an update
            if (!data) {
                // return window.dash_clientside.no_update;
                data = lowres[index];
            }
            //if (data == ori_figure.layout.images[0].source) {
            if (data == ori_figure.data[0].source) {
                return window.dash_clientside.no_update;
            }
            // Otherwise, perform update
            console.log("updating figure");
            let figure = {...ori_figure};
            //figure.layout.images[0].source = data;
            figure.data[0].source = data;
            return figure;
        }
        """.replace(
                "{{ID}}", self._id
            ),
            Output(self._subid("graph"), "figure"),
            [
                Input(self._subid("slice-index"), "data"),
                Input(self._subid("_slice-data"), "data"),
            ],
            [
                State(self._subid("graph"), "figure"),
                State(self._subid("_slice-data-lowres"), "data"),
            ],
        )
