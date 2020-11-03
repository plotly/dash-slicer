import numpy as np
from plotly.graph_objects import Figure, Image, Scatter
from dash import Dash
from dash.dependencies import Input, Output, State, ALL
from dash_core_components import Graph, Slider, Store

from .utils import img_array_to_uri, get_thumbnail_size_from_shape


class DashVolumeSlicer:
    """A slicer to show 3D image data in Dash.

    Parameters:
      app (dash.Dash): the Dash application instance.
      volume (ndarray): the 3D numpy array to slice through.
      axis (int): the dimension to slice in. Default 0.
      volume_id (str): the id to use for the volume. By default this is a
        hash of ``id(volume)``. Slicers that have the same volume-id show
        each-other's positions with line indicators.

    This is a placeholder object, not a Dash component. The components
    that make up the slicer can be accessed as attributes:

    * ``graph``: the Graph object.
    * ``slider``: the Slider object.
    * ``stores``: a list of Store objects. Some are "public" values, others
      used internally. Make sure to put them somewhere in the layout.

    Each component is given a dict-id with the following keys:

    * "context": a unique string id for this slicer instance.
    * "volume": the volume_id.
    * "axis": the int axis.
    * "name": the name of the component.

    TODO: iron out these details, list the stores that are public
    """

    _global_slicer_counter = 0

    def __init__(self, app, volume, axis=0, volume_id=None):
        if not isinstance(app, Dash):
            raise TypeError("Expect first arg to be a Dash app.")
        self._app = app
        # Check and store volume
        if not (isinstance(volume, np.ndarray) and volume.ndim == 3):
            raise TypeError("Expected volume to be a 3D numpy array")
        self._volume = volume
        # Check and store axis
        if not (isinstance(axis, int) and 0 <= axis <= 2):
            raise ValueError("The given axis must be 0, 1, or 2.")
        self._axis = int(axis)
        # Check and store id
        if volume_id is None:
            volume_id = hex(id(volume))
        elif not isinstance(volume_id, str):
            raise TypeError("volume_id must be a string")
        self.volume_id = volume_id
        # Get unique id scoped to this slicer object
        DashVolumeSlicer._global_slicer_counter += 1
        self.context_id = "slicer" + str(DashVolumeSlicer._global_slicer_counter)

        # Get the slice size (width, height), and max index
        arr_shape = list(volume.shape)
        arr_shape.pop(self._axis)
        self._slice_size = tuple(reversed(arr_shape))
        self._max_index = self._volume.shape[self._axis] - 1

        # Prep low-res slices
        thumbnail_size = get_thumbnail_size_from_shape(arr_shape, 32)
        thumbnails = [
            img_array_to_uri(self._slice(i), thumbnail_size)
            for i in range(self._max_index + 1)
        ]

        # Create a placeholder trace
        # todo: can add "%{z[0]}", but that would be the scaled value ...
        image_trace = Image(
            source="", dx=1, dy=1, hovertemplate="(%{x}, %{y})<extra></extra>"
        )
        scatter_trace = Scatter(x=[], y=[])  # placeholder
        # Create the figure object
        self._fig = fig = Figure(data=[image_trace, scatter_trace])
        fig.update_layout(
            template=None,
            margin=dict(l=0, r=0, b=0, t=0, pad=4),
        )
        fig.update_xaxes(
            # range=(0, slice_size[0]),
            showgrid=False,
            showticklabels=False,
            zeroline=False,
        )
        fig.update_yaxes(
            # range=(slice_size[1], 0),  # todo: allow flipping x or y
            showgrid=False,
            scaleanchor="x",
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
        # todo: use tooltip to show current value?
        self.slider = Slider(
            id=self._subid("slider"),
            min=0,
            max=self._max_index,
            step=1,
            value=self._max_index // 2,
            tooltip={"always_visible": False, "placement": "left"},
            updatemode="drag",
        )
        # Create the stores that we need (these must be present in the layout)
        self.stores = [
            Store(
                id=self._subid("_slice-size"), data=self._slice_size + thumbnail_size
            ),
            Store(id=self._subid("index"), data=volume.shape[self._axis] // 2),
            Store(id=self._subid("_requested-slice-index"), data=0),
            Store(id=self._subid("_slice-data"), data=""),
            Store(id=self._subid("_slice-data-lowres"), data=thumbnails),
            Store(id=self._subid("_indicators"), data=[]),
        ]

        self._create_server_callbacks()
        self._create_client_callbacks()

    def _subid(self, name):
        """Given a subid, get the full id including the slicer's prefix."""
        # return self.context_id + "-" + name
        # todo: is there a penalty for using a dict-id vs a string-id?
        return {
            "context": self.context_id,
            "volume-id": self.volume_id,
            "axis": self._axis,
            "name": name,
        }

    def _slice(self, index):
        """Sample a slice from the volume."""
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        im = self._volume[tuple(indices)]
        return (im.astype(np.float32) * (255 / im.max())).astype(np.uint8)

    def _create_server_callbacks(self):
        """Create the callbacks that run server-side."""
        app = self._app

        @app.callback(
            Output(self._subid("_slice-data"), "data"),
            [Input(self._subid("_requested-slice-index"), "data")],
        )
        def upload_requested_slice(slice_index):
            slice = self._slice(slice_index)
            return [slice_index, img_array_to_uri(slice)]

    def _create_client_callbacks(self):
        """Create the callbacks that run client-side."""
        app = self._app

        app.clientside_callback(
            """
        function handle_slider_move(index) {
            return index;
        }
        """,
            Output(self._subid("index"), "data"),
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
                "{{ID}}", self.context_id
            ),
            Output(self._subid("_requested-slice-index"), "data"),
            [Input(self._subid("index"), "data")],
        )

        # app.clientside_callback("""
        # function update_slider_pos(index) {
        #     return index;
        # }
        # """,
        #     [Output("index", "data")],
        #     [State("slider", "value")],
        # )

        app.clientside_callback(
            """
        function handle_incoming_slice(index, index_and_data, indicators, ori_figure, lowres, slice_size) {
            let new_index = index_and_data[0];
            let new_data = index_and_data[1];
            // Store data in cache
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            slice_cache[new_index] = new_data;
            // Get the data we need *now*
            let data = slice_cache[index];
            let x0 = 0, y0 = 0, dx = 1, dy = 1;
            //slice_cache[new_index] = undefined;  // todo: disabled cache for now!
            // Maybe we do not need an update
            console.log(slice_size)
            if (!data) {
                data = lowres[index];
                // Scale the image to take the exact same space as the full-res
                // version. It's not correct, but it looks better ...
                // slice_size = full_w, full_h, low_w, low_h
                dx = slice_size[0] / slice_size[2];
                dy = slice_size[1] / slice_size[3];
                x0 = 0.5 * dx - 0.5;
                y0 = 0.5 * dy - 0.5;
            }
            if (data == ori_figure.data[0].source && indicators.version == ori_figure.data[1].version) {
                return window.dash_clientside.no_update;
            }
            // Otherwise, perform update
            console.log("updating figure");
            let figure = {...ori_figure};
            figure.data[0].source = data;
            figure.data[0].x0 = x0;
            figure.data[0].y0 = y0;
            figure.data[0].dx = dx;
            figure.data[0].dy = dy;
            figure.data[1] = indicators;
            return figure;
        }
        """.replace(
                "{{ID}}", self.context_id
            ),
            Output(self._subid("graph"), "figure"),
            [
                Input(self._subid("index"), "data"),
                Input(self._subid("_slice-data"), "data"),
                Input(self._subid("_indicators"), "data"),
            ],
            [
                State(self._subid("graph"), "figure"),
                State(self._subid("_slice-data-lowres"), "data"),
                State(self._subid("_slice-size"), "data"),
            ],
        )

        # Select the *other* axii
        axii = [0, 1, 2]
        axii.pop(self._axis)

        # Create a callback to create a trace representing all slice-indices that:
        # * corresponding to the same volume data
        # * match any of the selected axii
        app.clientside_callback(
            """
        function handle_indicator(indices1, indices2, slice_size, current) {
            let w = slice_size[0], h = slice_size[1];
            let dx = w / 20, dy = h / 20;
            let version = (current.version || 0) + 1;
            let x = [], y = [];
            for (let index of indices1) {
                x.push(...[-dx, -1, null, w, w + dx, null]);
                y.push(...[index, index, index, index, index, index]);
            }
            for (let index of indices2) {
                x.push(...[index, index, index, index, index, index]);
                y.push(...[-dy, -1, null, h, h + dy, null]);
            }
            return {
                type: 'scatter',
                mode: 'lines',
                line: {color: '#ff00aa'},
                x: x,
                y: y,
                hoverinfo: 'skip',
                version: version
            }
        }
        """,
            Output(self._subid("_indicators"), "data"),
            [
                Input(
                    {
                        "volume-id": self.volume_id,
                        "context": ALL,
                        "name": "index",
                        "axis": axis,
                    },
                    "data",
                )
                for axis in axii
            ],
            [
                State(self._subid("_slice-size"), "data"),
                State(self._subid("_indicators"), "data"),
            ],
        )
