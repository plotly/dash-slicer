import numpy as np
from plotly.graph_objects import Figure
from dash import Dash
from dash.dependencies import Input, Output, State, ALL
from dash_core_components import Graph, Slider, Store

from .utils import img_array_to_uri, get_thumbnail_size, shape3d_to_size2d


class VolumeSlicer:
    """A slicer to show 3D image data in Dash.

    Parameters:
      app (dash.Dash): the Dash application instance.
      volume (ndarray): the 3D numpy array to slice through. The dimensions
        are assumed to be in zyx order. If this is not the case, you can
        use ``np.swapaxes`` to make it so.
      overlay (ndarray): a 3D numpy array of the same shape as volume, either
        boolean or uint8, describing an overlay mask. Default None.
      spacing (tuple of floats): The distance between voxels for each
        dimension (zyx).The spacing and origin are applied to make the slice
        drawn in "scene space" rather than "voxel space".
      origin (tuple of floats): The offset for each dimension (zyx).
      axis (int): the dimension to slice in. Default 0.
      reverse_y (bool): Whether to reverse the y-axis, so that the origin of
        the slice is in the top-left, rather than bottom-left. Default True.
        (This sets the figure's yaxes ``autorange`` to "reversed" or True.)
      scene_id (str): the scene that this slicer is part of. Slicers
        that have the same scene-id show each-other's positions with
        line indicators. By default this is derived from ``id(volume)``.

    This is a placeholder object, not a Dash component. The components
    that make up the slicer can be accessed as attributes. These must all
    be present in the app layout:

    * ``graph``: the dcc.Graph object. Use ``graph.figure`` to access the
      Plotly figure object.
    * ``slider``: the dcc.Slider object, its value represents the slice
      index. If you don't want to use the slider, wrap it in a div with
      style ``display: none``.
    * ``stores``: a list of dcc.Store objects.

    """

    _global_slicer_counter = 0

    def __init__(
        self,
        app,
        volume,
        overlay=None,
        *,
        spacing=None,
        origin=None,
        axis=0,
        reverse_y=True,
        scene_id=None,
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

        # Check and store overlay
        self.set_overlay(overlay)
        self._overlay_colormap = [(0, 0, 0, 0), (0, 255, 255, 100)]

        # Check and store axis
        if not (isinstance(axis, int) and 0 <= axis <= 2):
            raise ValueError("The given axis must be 0, 1, or 2.")
        self._axis = int(axis)
        self._reverse_y = bool(reverse_y)

        # Check and store scene id, and generate
        if scene_id is None:
            scene_id = "volume_" + hex(id(volume))[2:]
        elif not isinstance(scene_id, str):
            raise TypeError("scene_id must be a string")
        self._scene_id = scene_id

        # Get unique id scoped to this slicer object
        VolumeSlicer._global_slicer_counter += 1
        self._context_id = "slicer" + str(VolumeSlicer._global_slicer_counter)

        # Prepare slice info that we use at the client side
        self._slice_info = {
            "shape": tuple(volume.shape),
            "axis": self._axis,
            "size": shape3d_to_size2d(volume.shape, axis),
            "origin": shape3d_to_size2d(origin, axis),
            "spacing": shape3d_to_size2d(spacing, axis),
        }

        # Build the slicer
        self._create_dash_components()
        self._create_server_callbacks()
        self._create_client_callbacks()

    # Note(AK): we could make some stores public, but let's do this only when actual use-cases arise?

    @property
    def scene_id(self):
        """The id of the "virtual scene" for this slicer. Slicers that have
        the same scene_id show each-other's positions.
        """
        return self._scene_id

    @property
    def axis(self):
        """The axis at which the slicer is slicing."""
        return self._axis

    @property
    def graph(self):
        """The dcc.Graph for this slicer."""
        return self._graph

    @property
    def slider(self):
        """The dcc.Slider to change the index for this slicer."""
        return self._slider

    @property
    def stores(self):
        """A list of dcc.Store objects that the slicer needs to work.
        These must be added to the app layout.
        """
        return self._stores

    @property
    def refresh(self):
        """A stub dcc.Store. If a callback outputs to this store, it will
        force the figure to be updated, and the internal cache to be cleared.
        The value in this store has no significance.
        """
        return self._refresh

    def set_overlay(self, overlay):
        """Set the overlay data, a 3D numpy array of the same shape as
        the volume. Can be None to disable the overlay. Note that you
        should also output to ``this_slicer.refresh`` to trigger a redraw.
        """
        if overlay is not None:
            if overlay.dtype not in (np.bool, np.uint8):
                raise ValueError(
                    f"Overlay must have bool or uint8 dtype, not {overlay.dtype}."
                )
            if overlay.shape != self._volume.shape:
                raise ValueError(
                    f"Overlay must has shape {overlay.shape}, but expected {self._volume.shape}"
                )
        self._overlay = overlay

    def set_overlay_colormap(self, color):
        """Set the colormap of the overlay. The given color can be
        either a single RGBA color, or a list of colors (a colormap).
        Each color is an 4-element tuple of integers between 0 and 255.
        """
        color = np.array(color, np.uint8)
        if color.ndim == 1:
            if color.shape[0] != 4:
                raise ValueError("Overlay color must be 4 ints (0..255).")
            self._overlay_colormap = [(0, 0, 0, 0), tuple(color)]
        elif color.ndim == 2:
            if color.shape[1] != 4:
                raise ValueError("Overlay colors must be 4 ints (0..255).")
            self._overlay_colormap = [tuple(x) for x in color]
        else:
            raise ValueError(
                "Overlay color must be a single color or a list of colors."
            )

    def _subid(self, name, use_dict=False):
        """Given a name, get the full id including the context id prefix."""
        if use_dict:
            # A dict-id is nice to query objects with pattern matching callbacks,
            # and we use that to show the position of other sliders. But it makes
            # the id's very long, which is annoying e.g. in the callback graph.
            return {
                "context": self._context_id,
                "scene": self._scene_id,
                "axis": self._axis,
                "name": name,
            }
        else:
            return self._context_id + "-" + name

    def _slice(self, index):
        """Sample a slice from the volume."""
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        im = self._volume[tuple(indices)]
        return (im.astype(np.float32) * (255 / im.max())).astype(np.uint8)

    def _slice_overlay(self, index):
        """Sample a slice from the overlay. returns either None or an rgba image."""
        overlay = self._overlay
        if overlay is None:
            return None
        overlay = overlay.astype(np.uint8, copy=False)  # need int to index
        # Sample the slice
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        im = overlay[tuple(indices)]
        max_mask = im.max()
        # If the mask is all zeros, we can simply not draw it.
        if max_mask == 0:
            return None
        # Turn into rgba
        colormap = self._overlay_colormap
        while len(colormap) <= max_mask:
            colormap.append(colormap[-1])
        colormap = np.array(colormap)
        rgba = colormap[im]
        return rgba

    def _create_dash_components(self):
        """Create the graph, slider, figure, etc."""
        info = self._slice_info

        # Prep low-res slices
        thumbnail_size = get_thumbnail_size(info["size"][:2], (32, 32))
        thumbnails = [
            img_array_to_uri(self._slice(i), thumbnail_size)
            for i in range(info["size"][2])
        ]
        info["lowres_size"] = thumbnail_size

        # Create the figure object - can be accessed by user via slicer.graph.figure
        self._fig = fig = Figure(data=[])
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
            autorange="reversed" if self._reverse_y else True,
        )

        # Create the graph (graph is a Dash component wrapping a Plotly figure)
        self._graph = Graph(
            id=self._subid("graph"),
            figure=fig,
            config={"scrollZoom": True},
        )

        # Create a slider object that the user can put in the layout (or not)
        self._slider = Slider(
            id=self._subid("slider"),
            min=0,
            max=info["size"][2] - 1,
            step=1,
            value=info["size"][2] // 2,
            tooltip={"always_visible": False, "placement": "left"},
            updatemode="drag",
        )

        # Create the stores that we need (these must be present in the layout)
        self._refresh = Store(id=self._subid("refresh"), data=None)
        self._info = Store(id=self._subid("info"), data=info)
        self._position = Store(id=self._subid("position", True), data=0)
        self._requested_index = Store(id=self._subid("req-index"), data=0)
        self._request_data = Store(id=self._subid("req-data"), data="")
        self._lowres_data = Store(id=self._subid("lowres-data"), data=thumbnails)
        self._img_traces = Store(id=self._subid("img-traces"), data=[])
        self._indicator_traces = Store(id=self._subid("indicator-traces"), data=[])
        self._stores = [
            self._refresh,
            self._info,
            self._position,
            self._requested_index,
            self._request_data,
            self._lowres_data,
            self._img_traces,
            self._indicator_traces,
        ]

    def _create_server_callbacks(self):
        """Create the callbacks that run server-side."""
        app = self._app

        @app.callback(
            Output(self._request_data.id, "data"),
            [Input(self._requested_index.id, "data"), Input(self._refresh.id, "data")],
        )
        def upload_requested_slice(slice_index, refresh):
            slice = img_array_to_uri(self._slice(slice_index))
            overlay = self._slice_overlay(slice_index)
            overlay = None if overlay is None else img_array_to_uri(overlay)
            return {"index": slice_index, "slice": slice, "overlay": overlay}

    def _create_client_callbacks(self):
        """Create the callbacks that run client-side."""
        app = self._app

        # ----------------------------------------------------------------------
        # Callback to update position (in scene coordinates) from the index.

        app.clientside_callback(
            """
        function update_position(index, info) {
            return info.origin[2] + index * info.spacing[2];
        }
        """,
            Output(self._position.id, "data"),
            [Input(self.slider.id, "value")],
            [State(self._info.id, "data")],
        )

        # ----------------------------------------------------------------------
        # Callback to request new slices.
        # Note: this callback cannot be merged with the one below, because
        # it would create a circular dependency.

        app.clientside_callback(
            """
        function update_request(refresh, index) {

            // Clear the cache?
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            for (let trigger of dash_clientside.callback_context.triggered) {
                if (trigger.prop_id.indexOf('refresh') >= 0) {
                    slice_cache = window.slicecache_for_{{ID}} = {};
                    break;
                }
            }

            // Request a new slice (or not)
            let request_index = index;
            if (slice_cache[index]) {
                return window.dash_clientside.no_update;
            } else {
                console.log('request slice ' + index);
                return index;
            }
        }
        """.replace(
                "{{ID}}", self._context_id
            ),
            Output(self._requested_index.id, "data"),
            [Input(self._refresh.id, "data"), Input(self.slider.id, "value")],
        )

        # ----------------------------------------------------------------------
        # Callback that creates a list of image traces (slice and overlay).

        app.clientside_callback(
            """
        function update_image_traces(index, req_data, lowres, info, current_traces) {

            // Add data to the cache if the data is indeed new
            if (!window.slicecache_for_{{ID}}) { window.slicecache_for_{{ID}} = {}; }
            let slice_cache = window.slicecache_for_{{ID}};
            for (let trigger of dash_clientside.callback_context.triggered) {
                if (trigger.prop_id.indexOf('req-data') >= 0) {
                    slice_cache[req_data.index] = req_data;
                    break;
                }
            }

            // Prepare traces
            let slice_trace = {
                type: 'image',
                x0: info.origin[0],
                y0: info.origin[1],
                dx: info.spacing[0],
                dy: info.spacing[1],
                hovertemplate: '(%{x:.2f}, %{y:.2f})<extra></extra>'
            };
            let overlay_trace = {...slice_trace};
            overlay_trace.hoverinfo = 'skip';
            overlay_trace.hovertemplate = '';
            let new_traces = [slice_trace, overlay_trace];

            // Depending on the state of the cache, use full data, or use lowres and request slice
            if (slice_cache[index]) {
                let cached = slice_cache[index];
                slice_trace.source = cached.slice;
                overlay_trace.source = cached.overlay || "";
            } else {
                slice_trace.source = lowres[index];
                overlay_trace.source = "";
                // Scale the image to take the exact same space as the full-res
                // version. It's not correct, but it looks better ...
                slice_trace.dx *= info.size[0] / info.lowres_size[0];
                slice_trace.dy *= info.size[1] / info.lowres_size[1];
                slice_trace.x0 += 0.5 * slice_trace.dx - 0.5 * info.spacing[0];
                slice_trace.y0 += 0.5 * slice_trace.dy - 0.5 * info.spacing[1];
            }

            // Has the image data even changed?
            if (!current_traces.length) { current_traces = [{source:''}, {source:''}]; }
            if (new_traces[0].source == current_traces[0].source &&
                new_traces[1].source == current_traces[1].source)
            {
                new_traces = window.dash_clientside.no_update;
            }
            return new_traces;
        }
        """.replace(
                "{{ID}}", self._context_id
            ),
            Output(self._img_traces.id, "data"),
            [Input(self.slider.id, "value"), Input(self._request_data.id, "data")],
            [
                State(self._lowres_data.id, "data"),
                State(self._info.id, "data"),
                State(self._img_traces.id, "data"),
            ],
        )

        # ----------------------------------------------------------------------
        # Callback to create scatter traces from the positions of other slicers.

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
            return [{
                type: 'scatter',
                mode: 'lines',
                line: {color: '#ff00aa'},
                x: x,
                y: y,
                hoverinfo: 'skip',
                version: version
            }];
        }
        """,
            Output(self._indicator_traces.id, "data"),
            [
                Input(
                    {
                        "scene": self._scene_id,
                        "context": ALL,
                        "name": "position",
                        "axis": axis,
                    },
                    "data",
                )
                for axis in axii
            ],
            [
                State(self._info.id, "data"),
                State(self._indicator_traces.id, "data"),
            ],
        )

        # ----------------------------------------------------------------------
        # Callback that composes a figure from multiple trace sources.

        app.clientside_callback(
            """
        function update_figure(img_traces, indicators, ori_figure) {

            // Collect traces
            let traces = [];
            for (let trace of img_traces) { traces.push(trace); }
            for (let trace of indicators) { traces.push(trace); }

            // Update figure
            console.log("updating figure");
            let figure = {...ori_figure};
            figure.data = traces;
            return figure;
        }
        """,
            Output(self.graph.id, "figure"),
            [
                Input(self._img_traces.id, "data"),
                Input(self._indicator_traces.id, "data"),
            ],
            [
                State(self.graph.id, "figure"),
            ],
        )
