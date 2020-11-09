import numpy as np
from plotly.graph_objects import Figure, Image, Scatter
from dash import Dash
from dash.dependencies import Input, Output, State, ALL
from dash_core_components import Graph, Slider, Store

from .utils import img_array_to_uri, get_thumbnail_size_from_shape, shape3d_to_size2d


class VolumeSlicer:
    """A slicer to show 3D image data in Dash.

    Parameters:
      app (dash.Dash): the Dash application instance.
      volume (ndarray): the 3D numpy array to slice through. The dimensions
        are assumed to be in zyx order. If this is not the case, you can
        use ``np.swapaxes`` to make it so.
      spacing (tuple of floats): The distance between voxels for each dimension (zyx).
        The spacing and origin are applied to make the slice drawn in
        "scene space" rather than "voxel space".
      origin (tuple of floats): The offset for each dimension (zyx).
      axis (int): the dimension to slice in. Default 0.
      reverse_y (bool): Whether to reverse the y-axis, so that the origin of
        the slice is in the top-left, rather than bottom-left. Default True.
        (This sets the figure's yaxes ``autorange`` to either "reversed" or True.)
      scene_id (str): the scene that this slicer is part of. Slicers
        that have the same scene-id show each-other's positions with
        line indicators. By default this is derived from ``id(volume)``.

    This is a placeholder object, not a Dash component. The components
    that make up the slicer can be accessed as attributes:

    * ``graph``: the dcc.Graph object.
    * ``graph.figure``: the Plotly figure object.
    * ``slider``: the dcc.Slider object, its value represents the slice index.
    * ``stores``: a list of dcc.Store objects. Some are "public" values, others
      used internally. Make sure to put them somewhere in the layout.

    Each component is given a dict-id with the following keys:

    * "context": a unique string id for this slicer instance.
    * "scene": the scene_id.
    * "axis": the int axis.
    * "name": the name of the (sub) component.

    TODO: iron out these details, list the stores that are public
    """

    _global_slicer_counter = 0

    def __init__(
        self,
        app,
        volume,
        *,
        spacing=None,
        origin=None,
        axis=0,
        reverse_y=True,
        scene_id=None
    ):
        if not isinstance(app, Dash):
            raise TypeError("Expect first arg to be a Dash app.")
        self._app = app
        # Check and store volume
        if not (isinstance(volume, np.ndarray) and volume.ndim == 3):
            raise TypeError("Expected volume to be a 3D numpy array")
        self._volume = volume
        spacing = (1, 1, 1) if spacing is None else spacing
        spacing = float(spacing[0]), float(spacing[1]), float(spacing[2])
        origin = (0, 0, 0) if origin is None else origin
        origin = float(origin[0]), float(origin[1]), float(origin[2])
        # Check and store axis
        if not (isinstance(axis, int) and 0 <= axis <= 2):
            raise ValueError("The given axis must be 0, 1, or 2.")
        self._axis = int(axis)
        # Check and store id
        if scene_id is None:
            scene_id = "volume_" + hex(id(volume))[2:]
        elif not isinstance(scene_id, str):
            raise TypeError("scene_id must be a string")
        self.scene_id = scene_id
        # Get unique id scoped to this slicer object
        VolumeSlicer._global_slicer_counter += 1
        self.context_id = "slicer_" + str(VolumeSlicer._global_slicer_counter)

        # Prepare slice info
        info = {
            "shape": tuple(volume.shape),
            "axis": self._axis,
            "size": shape3d_to_size2d(volume.shape, axis),
            "origin": shape3d_to_size2d(origin, axis),
            "spacing": shape3d_to_size2d(spacing, axis),
        }

        # Prep low-res slices
        thumbnail_size = get_thumbnail_size_from_shape(
            (info["size"][1], info["size"][0]), 32
        )
        thumbnails = [
            img_array_to_uri(self._slice(i), thumbnail_size)
            for i in range(info["size"][2])
        ]
        info["lowres_size"] = thumbnail_size

        # Create traces
        # todo: can add "%{z[0]}", but that would be the scaled value ...
        image_trace = Image(
            source="", dx=1, dy=1, hovertemplate="(%{x}, %{y})<extra></extra>"
        )
        scatter_trace = Scatter(x=[], y=[])  # placeholder
        # Create the figure object - can be accessed by user via slicer.graph.figure
        self._fig = fig = Figure(data=[image_trace, scatter_trace])
        fig.update_layout(
            template=None,
            margin=dict(l=0, r=0, b=0, t=0, pad=4),
        )
        fig.update_xaxes(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
        )
        fig.update_yaxes(
            showgrid=False,
            scaleanchor="x",
            showticklabels=False,
            zeroline=False,
            autorange="reversed" if reverse_y else True,
        )
        # Create the graph (graph is a Dash component wrapping a Plotly figure)
        self.graph = Graph(
            id=self._subid("graph"),
            figure=fig,
            config={"scrollZoom": True},
        )
        # Create a slider object that the user can put in the layout (or not)
        self.slider = Slider(
            id=self._subid("slider"),
            min=0,
            max=info["size"][2] - 1,
            step=1,
            value=info["size"][2] // 2,
            tooltip={"always_visible": False, "placement": "left"},
            updatemode="drag",
        )
        # Create the stores that we need (these must be present in the layout)
        self.stores = [
            Store(id=self._subid("info"), data=info),
            Store(id=self._subid("position"), data=0),
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
            "scene": self.scene_id,
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
        function update_position(index, info) {
            return info.origin[2] + index * info.spacing[2];
        }
        """,
            Output(self._subid("position"), "data"),
            [Input(self._subid("slider"), "value")],
            [State(self._subid("info"), "data")],
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
            [Input(self._subid("slider"), "value")],
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
        function handle_incoming_slice(index, index_and_data, indicators, ori_figure, lowres, info) {
            let new_index = index_and_data[0];
            let new_data = index_and_data[1];
            // Store data in cache
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            slice_cache[new_index] = new_data;
            // Get the data we need *now*
            let data = slice_cache[index];
            let x0 = info.origin[0], y0 = info.origin[1];
            let dx = info.spacing[0], dy = info.spacing[1];
            //slice_cache[new_index] = undefined;  // todo: disabled cache for now!
            // Maybe we do not need an update
            if (!data) {
                data = lowres[index];
                // Scale the image to take the exact same space as the full-res
                // version. It's not correct, but it looks better ...
                dx *= info.size[0] / info.lowres_size[0];
                dy *= info.size[1] / info.lowres_size[1];
                x0 += 0.5 * dx - 0.5 * info.spacing[0];
                y0 += 0.5 * dy - 0.5 * info.spacing[1];
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
                Input(self._subid("slider"), "value"),
                Input(self._subid("_slice-data"), "data"),
                Input(self._subid("_indicators"), "data"),
            ],
            [
                State(self._subid("graph"), "figure"),
                State(self._subid("_slice-data-lowres"), "data"),
                State(self._subid("info"), "data"),
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
        function handle_indicator(positions1, positions2, info, current) {
            let x0 = info.origin[0], y0 = info.origin[1];
            let x1 = x0 + info.size[0] * info.spacing[0], y1 = y0 + info.size[1] * info.spacing[1];
            x0 = x0 - info.spacing[0], y0 = y0 - info.spacing[1];
            let d = ((x1 - x0) + (y1 - y0)) * 0.5 * 0.05;
            let version = (current.version || 0) + 1;
            let x = [], y = [];
            for (let pos of positions1) {
                // x relative to our slice, y in scene-coords
                x.push(...[x0 - d, x0, null, x1, x1 + d, null]);
                y.push(...[pos, pos, pos, pos, pos, pos]);
            }
            for (let pos of positions2) {
                // x in scene-coords, y relative to our slice
                x.push(...[pos, pos, pos, pos, pos, pos]);
                y.push(...[y0 - d, y0, null, y1, y1 + d, null]);
            }
            return {
                type: 'scatter',
                mode: 'lines',
                line: {color: '#ff00aa'},
                x: x,
                y: y,
                hoverinfo: 'skip',
                version: version
            };
        }
        """,
            Output(self._subid("_indicators"), "data"),
            [
                Input(
                    {
                        "scene": self.scene_id,
                        "context": ALL,
                        "name": "position",
                        "axis": axis,
                    },
                    "data",
                )
                for axis in axii
            ],
            [
                State(self._subid("info"), "data"),
                State(self._subid("_indicators"), "data"),
            ],
        )
