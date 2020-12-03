import numpy as np
import plotly
import dash
from dash.dependencies import Input, Output, State, ALL
from dash_core_components import Graph, Slider, Store, Interval

from .utils import img_array_to_uri, get_thumbnail_size, shape3d_to_size2d


# The default colors to use for indicators and overlays
discrete_colors = plotly.colors.qualitative.D3

_assigned_scene_ids = {}  # id(volume) -> str


class VolumeSlicer:
    """A slicer to show 3D image data in Dash.

    Parameters:
      app (dash.Dash): the Dash application instance.
      volume (ndarray): the 3D numpy array to slice through. The dimensions
        are assumed to be in zyx order. If this is not the case, you can
        use ``np.swapaxes`` to make it so.
      spacing (tuple of floats): The distance between voxels for each
        dimension (zyx).The spacing and origin are applied to make the slice
        drawn in "scene space" rather than "voxel space".
      origin (tuple of floats): The offset for each dimension (zyx).
      axis (int): the dimension to slice in. The default 0.
      reverse_y (bool): Whether to reverse the y-axis, so that the origin of
        the slice is in the top-left, rather than bottom-left. Default True.
        (This sets the figure's yaxes ``autorange`` to "reversed" or True.)
        Note: setting this to False affects performance, see #12.
      scene_id (str): the scene that this slicer is part of. Slicers
        that have the same scene-id show each-other's positions with
        line indicators. By default this is derived from ``id(volume)``.
      color (str): the color for this slicer. By default the color is
        red, green, or blue, depending on the axis. Set to empty string
        for "no color".

    This is a placeholder object, not a Dash component. The components
    that make up the slicer can be accessed as attributes. These must all
    be present in the app layout:

    * ``graph``: the dcc.Graph object. Use ``graph.figure`` to access the
      Plotly Figure object.
    * ``slider``: the dcc.Slider object, its value represents the slice
      index. If you don't want to use the slider, wrap it in a div with
      style ``display: none``.
    * ``stores``: a list of dcc.Store objects.

    To programatically set the position of the slicer, use a store with
    a dictionary-id with the following fields:

    * 'context': a unique name for this store.
    * 'scene': the scene_id for which to set the position
    * 'name': 'setpos'

    The value in the store must be an 3-element tuple (x, y, z) in scene coordinates.
    To apply the position for one position only, use e.g ``(None, None, x)``.

    Some notes on performance: for a smooth experience, avoid triggering
    unnecessary figure updates. When adding a callback that uses the
    slicer position, use the (rate limited) `index` and `pos` stores
    rather than the slider value. Further, create the `Dash` application
    with `update_title=None`, and when running the server in debug mode,
    consider setting `dev_tools_props_check=False`.

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
        scene_id=None,
        color=None,
    ):

        if not isinstance(app, dash.Dash):
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
        self._reverse_y = bool(reverse_y)

        # Check and store scene id, and generate
        if scene_id is None:
            n = len(_assigned_scene_ids)
            scene_id = _assigned_scene_ids.setdefault(id(volume), f"vol{n}")
        elif not isinstance(scene_id, str):
            raise TypeError("scene_id must be a string")
        self._scene_id = scene_id

        # Check color
        if color is None:
            color = discrete_colors[self._axis]

        # Get unique id scoped to this slicer object
        VolumeSlicer._global_slicer_counter += 1
        self._context_id = "slicer" + str(VolumeSlicer._global_slicer_counter)

        # Prepare slice info that we use at the client side.
        # Note that shape, origin and spacing are in zyx order.
        # The size, offset, stepsize are in xyz local to the slicer
        # (z is in direction of the axis).
        self._slice_info = {
            "axis": self._axis,
            "size": shape3d_to_size2d(volume.shape, axis),
            "offset": shape3d_to_size2d(origin, axis),
            "stepsize": shape3d_to_size2d(spacing, axis),
            "color": color,
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
    def nslices(self):
        """The number of slices for this slicer."""
        return self._volume.shape[self._axis]

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
    def state(self):
        """A dcc.Store representing the current state of the slicer (present
        in slicer.stores). Its data is a dict with the fields:
        index (int), pos (float), axis (int), color (str).

        Its id is a dictionary so it can be used in a pattern matching Input.
        Fields: context, scene, name. Where scene is the scene_id and name is "state".
        """
        return self._state

    @property
    def overlay_data(self):
        """A dcc.Store containing the overlay data. The form of this
        data is considered an implementation detail; users are expected to use
        ``create_overlay_data`` to create it.
        """
        return self._overlay_data

    def create_overlay_data(self, mask, color=None):
        """Given a 3D mask array and an index, create an object that
        can be used as output for ``slicer.overlay_data``. The color
        can be an rgb/rgba tuple, or a hex color. Alternatively, color
        can be a list of such colors, defining a colormap.
        """
        # Check the mask
        if mask.dtype not in (np.bool, np.uint8):
            raise ValueError(f"Mask must have bool or uint8 dtype, not {mask.dtype}.")
        if mask.shape != self._volume.shape:
            raise ValueError(
                f"Overlay must has shape {mask.shape}, but expected {self._volume.shape}"
            )
        mask = mask.astype(np.uint8, copy=False)  # need int to index

        # Create a colormap (list) from the given color(s)
        if color is None:
            colormap = discrete_colors[3:]
        elif isinstance(color, (tuple, list)) and all(
            isinstance(x, (int, float)) for x in color
        ):
            colormap = [color]
        else:
            colormap = list(color)

        # Normalize the colormap so each element is a 4-element tuple
        for i in range(len(colormap)):
            c = colormap[i]
            if isinstance(c, str):
                if c.startswith("#"):
                    c = plotly.colors.hex_to_rgb(c)
                else:
                    raise ValueError(
                        "Named colors are not (yet) supported, hex colors are."
                    )
            c = tuple(int(x) for x in c)
            if len(c) == 3:
                c = c + (100,)
            elif len(c) != 4:
                raise ValueError("Expected color tuples to be 3 or 4 elements.")
            colormap[i] = c

        # Insert zero stub color for where mask is zero
        colormap.insert(0, (0, 0, 0, 0))

        # Produce slices (base64 png strings)
        overlay_slices = []
        for index in range(self.nslices):
            # Sample the slice
            indices = [slice(None), slice(None), slice(None)]
            indices[self._axis] = index
            im = mask[tuple(indices)]
            max_mask = im.max()
            if max_mask == 0:
                # If the mask is all zeros, we can simply not draw it
                overlay_slices.append(None)
            else:
                # Turn into rgba
                while len(colormap) <= max_mask:
                    colormap.append(colormap[-1])
                colormap_arr = np.array(colormap)
                rgba = colormap_arr[im]
                overlay_slices.append(img_array_to_uri(rgba))

        return overlay_slices

    def _subid(self, name, use_dict=False, **kwargs):
        """Given a name, get the full id including the context id prefix."""
        if use_dict:
            # A dict-id is nice to query objects with pattern matching callbacks,
            # and we use that to show the position of other sliders. But it makes
            # the id's very long, which is annoying e.g. in the callback graph.
            d = {
                "context": self._context_id,
                "scene": self._scene_id,
                "name": name,
            }
            d.update(kwargs)
            return d
        else:
            assert not kwargs
            return self._context_id + "-" + name

    def _slice(self, index):
        """Sample a slice from the volume."""
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        im = self._volume[tuple(indices)]
        return (im.astype(np.float32) * (255 / im.max())).astype(np.uint8)

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
        self._fig = fig = plotly.graph_objects.Figure(data=[])
        fig.update_layout(
            template=None,
            margin={"l": 0, "r": 0, "b": 0, "t": 0, "pad": 4},
            dragmode="pan",  # good default mode
        )
        fig.update_xaxes(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            constrain="range",
        )
        fig.update_yaxes(
            showgrid=False,
            scaleanchor="x",
            showticklabels=False,
            zeroline=False,
            autorange="reversed" if self._reverse_y else True,
            constrain="range",
        )

        # Create the graph (graph is a Dash component wrapping a Plotly figure)
        self._graph = Graph(
            id=self._subid("graph"),
            figure=fig,
            config={"scrollZoom": True},
        )

        initial_index = info["size"][2] // 2
        initial_state = {
            "index": initial_index,
            "pos": info["offset"][2] + initial_index * info["stepsize"][2],
            "axis": info["axis"],
            "color": info["color"],
        }

        # Create a slider object that the user can put in the layout (or not).
        # Note that the tooltip introduces a measurable performance penalty,
        # so maybe we can display it in a different way?
        self._slider = Slider(
            id=self._subid("slider"),
            min=0,
            max=info["size"][2] - 1,
            step=1,
            value=initial_index,
            updatemode="drag",
            tooltip={"always_visible": False, "placement": "left"},
        )

        # Create the stores that we need (these must be present in the layout)

        # A dict of static info for this slicer
        self._info = Store(id=self._subid("info"), data=info)

        # A list of low-res slices (encoded as base64-png)
        self._lowres_data = Store(id=self._subid("lowres"), data=thumbnails)

        # A list of mask slices (encoded as base64-png or null)
        self._overlay_data = Store(id=self._subid("overlay"), data=[])

        # Slice data provided by the server
        self._server_data = Store(id=self._subid("server-data"), data="")

        # Store image traces for the slicer.
        self._img_traces = Store(id=self._subid("img-traces"), data=[])

        # Store indicator traces for the slicer.
        self._indicator_traces = Store(id=self._subid("indicator-traces"), data=[])

        # A timer to apply a rate-limit between slider.value and index.data
        self._timer = Interval(id=self._subid("timer"), interval=100, disabled=True)

        # The (public) state of the slicer. This value is rate-limited
        self._state = Store(id=self._subid("state", True), data=initial_state)

        # Signal to set the position of other slicers with the same scene_id.
        self._setpos = Store(id=self._subid("setpos", True), data=None)

        self._stores = [
            self._info,
            self._lowres_data,
            self._overlay_data,
            self._server_data,
            self._img_traces,
            self._indicator_traces,
            self._timer,
            self._state,
            self._setpos,
        ]

    def _create_server_callbacks(self):
        """Create the callbacks that run server-side."""
        app = self._app

        @app.callback(
            Output(self._server_data.id, "data"),
            [Input(self._state.id, "data")],
        )
        def upload_requested_slice(state):
            index = state["index"]
            slice = img_array_to_uri(self._slice(index))
            return {"index": index, "slice": slice}

    def _create_client_callbacks(self):
        """Create the callbacks that run client-side."""

        # setpos (external)
        #     \
        #     slider  --[rate limit]-->  state
        #         \                         \
        #          \                   server_data (a new slice)
        #           \                         \
        #            \                         -->  image_traces
        #             ----------------------- /           \
        #                                                  ----->  figure
        #                                                 /
        #                                      indicator_traces
        #                                               /
        #                                             state (external)

        app = self._app

        # ----------------------------------------------------------------------
        # Callback to trigger fellow slicers to go to a specific position on click.

        app.clientside_callback(
            """
        function update_setpos_from_click(data, index, info) {
            if (data && data.points && data.points.length) {
                let point = data["points"][0];
                let xyz = [point["x"], point["y"]];
                let depth = info.offset[2] + index * info.stepsize[2];
                xyz.splice(2 - info.axis, 0, depth);
                return xyz;
            }
            return dash_clientside.no_update;
        }
        """,
            Output(self._setpos.id, "data"),
            [Input(self._graph.id, "clickData")],
            [State(self._slider.id, "value"), State(self._info.id, "data")],
        )

        # ----------------------------------------------------------------------
        # Callback to update slider based on external setpos signals.

        app.clientside_callback(
            """
        function update_slider_value(positions, cur_index, info) {
            for (let trigger of dash_clientside.callback_context.triggered) {
                if (!trigger.value) continue;
                let pos = trigger.value[2 - info.axis];
                if (typeof pos !== 'number') continue;
                let index = Math.round((pos - info.offset[2]) / info.stepsize[2]);
                if (index == cur_index) continue;
                return Math.max(0, Math.min(info.size[2] - 1, index));
            }
            return dash_clientside.no_update;
        }
        """,
            Output(self._slider.id, "value"),
            [
                Input(
                    {
                        "scene": self._scene_id,
                        "context": ALL,
                        "name": "setpos",
                    },
                    "data",
                )
            ],
            [State(self._slider.id, "value"), State(self._info.id, "data")],
        )

        # ----------------------------------------------------------------------
        # Callback to rate-limit the index (using a timer/interval).

        app.clientside_callback(
            """
        function update_index_rate_limiting(index, n_intervals, interval, info) {

            if (!window._slicer_{{ID}}) window._slicer_{{ID}} = {};
            let private_state = window._slicer_{{ID}};
            let now = window.performance.now();

            // Get whether the slider was moved
            let slider_was_moved = false;
            for (let trigger of dash_clientside.callback_context.triggered) {
                if (trigger.prop_id.indexOf('slider') >= 0) slider_was_moved = true;
            }

            // Initialize return values
            let new_state = dash_clientside.no_update;
            let disable_timer = false;

            // If the slider moved, remember the time when this happened
            private_state.new_time = private_state.new_time || 0;

            if (slider_was_moved) {
                private_state.new_time = now;
            } else if (!n_intervals) {
                disable_timer = true;  // start disabled
            }

            // We can either update the rate-limited index interval ms after
            // the real index changed, or interval ms after it stopped
            // changing. The former makes the indicators come along while
            // dragging the slider, the latter is better for a smooth
            // experience, and the interval can be set much lower.
            if (index != private_state.index) {
                if (now - private_state.new_time >= interval) {
                    private_state.index = index;
                    disable_timer = true;
                    console.log('requesting slice ' + index);
                    new_state = {
                        index: index,
                        pos: info.offset[2] + index * info.stepsize[2],
                        axis: info.axis,
                        color: info.color,
                    };
                }
            }

            return [new_state, disable_timer];
        }
        """.replace(
                "{{ID}}", self._context_id
            ),
            [
                Output(self._state.id, "data"),
                Output(self._timer.id, "disabled"),
            ],
            [Input(self._slider.id, "value"), Input(self._timer.id, "n_intervals")],
            [
                State(self._timer.id, "interval"),
                State(self._info.id, "data"),
            ],
        )

        # todo: include info about axis range in state

        # ----------------------------------------------------------------------
        # Callback that creates a list of image traces (slice and overlay).

        app.clientside_callback(
            """
        function update_image_traces(index, server_data, overlays, lowres, info, current_traces) {

            // Prepare traces
            let slice_trace = {
                type: 'image',
                x0: info.offset[0],
                y0: info.offset[1],
                dx: info.stepsize[0],
                dy: info.stepsize[1],
                hovertemplate: '(%{x:.2f}, %{y:.2f})<extra></extra>'
            };
            let overlay_trace = {...slice_trace};
            overlay_trace.hoverinfo = 'skip';
            overlay_trace.source = overlays[index] || '';
            overlay_trace.hovertemplate = '';
            let new_traces = [slice_trace, overlay_trace];

            // Use full data, or use lowres
            if (index == server_data.index) {
                slice_trace.source = server_data.slice;
            } else {
                slice_trace.source = lowres[index];
                // Scale the image to take the exact same space as the full-res
                // version. Note that depending on how the low-res data is
                // created, the pixel centers may not be correctly aligned.
                slice_trace.dx *= info.size[0] / info.lowres_size[0];
                slice_trace.dy *= info.size[1] / info.lowres_size[1];
                slice_trace.x0 += 0.5 * slice_trace.dx - 0.5 * info.stepsize[0];
                slice_trace.y0 += 0.5 * slice_trace.dy - 0.5 * info.stepsize[1];
            }

            // Has the image data even changed?
            if (!current_traces.length) { current_traces = [{source:''}, {source:''}]; }
            if (new_traces[0].source == current_traces[0].source &&
                new_traces[1].source == current_traces[1].source)
            {
                new_traces = dash_clientside.no_update;
            }
            return new_traces;
        }
        """.replace(
                "{{ID}}", self._context_id
            ),
            Output(self._img_traces.id, "data"),
            [
                Input(self._slider.id, "value"),
                Input(self._server_data.id, "data"),
                Input(self._overlay_data.id, "data"),
            ],
            [
                State(self._lowres_data.id, "data"),
                State(self._info.id, "data"),
                State(self._img_traces.id, "data"),
            ],
        )

        # ----------------------------------------------------------------------
        # Callback to create scatter traces from the positions of other slicers.

        app.clientside_callback(
            """
        function update_indicator_traces(states, info) {
            let x0 = info.offset[0], y0 = info.offset[1];
            let x1 = x0 + info.size[0] * info.stepsize[0], y1 = y0 + info.size[1] * info.stepsize[1];
            x0 = x0 - info.stepsize[0], y0 = y0 - info.stepsize[1];
            let d = ((x1 - x0) + (y1 - y0)) * 0.5 * 0.05;

            let axii = [0, 1, 2];
            axii.splice(info.axis, 1);
            let traces = [];

            for (let state of states) {
                let pos = state.pos;
                if (state.axis == axii[0]) {
                    // x relative to our slice, y in scene-coords
                    traces.push({
                        //x: [x0 - d, x0, null, x1, x1 + d, null],
                        x: [x0, x1],
                        y: [pos, pos],
                        line: {color: state.color, width: 1}
                    });
                } else if (state.axis == axii[1]) {
                    // x in scene-coords, y relative to our slice
                    traces.push({
                        x: [pos, pos],
                        y: [y0, y1],
                        //y: [y0 - d, y0, null, y1, y1 + d, null],
                        line: {color: state.color, width: 1}
                    });
                }
            }

            for (let trace of traces) {
                trace.type = 'scatter';
                trace.mode = 'lines';
                trace.hoverinfo = 'skip';
                trace.showlegend = false;
            }

            return traces;
        }
        """,
            Output(self._indicator_traces.id, "data"),
            [
                Input(
                    {
                        "scene": self._scene_id,
                        "context": ALL,
                        "name": "state",
                    },
                    "data",
                )
            ],
            [
                State(self._info.id, "data"),
            ],
        )

        # ----------------------------------------------------------------------
        # Callback that composes a figure from multiple trace sources.

        app.clientside_callback(
            """
        function update_figure(img_traces, indicators, ori_figure, info) {

            // Collect traces
            let traces = [];
            for (let trace of img_traces) { traces.push(trace); }
            for (let trace of indicators) { if (trace.line.color) traces.push(trace); }

            // Show our own color as a rectangle around the image, but only if
            // there are other slicers with the same scene id, on a different axis.
            // We do some math to make sure that these indicators are the same
            // size (in scene coordinates) for all slicers of the same data.
            if (indicators.length > 0 && info.color) {
                let fraction, x1, x2, x3, x4, y1, y2, y3, y4, z1, z4, dd;
                fraction = 0.1;
                x1 = info.offset[0] - info.stepsize[0]/2;
                y1 = info.offset[1] - info.stepsize[1]/2;
                z1 = info.offset[2] - info.stepsize[2]/2;
                x4 = info.offset[0] + (info.size[0] - 0.5) * info.stepsize[0];
                y4 = info.offset[1] + (info.size[1] - 0.5) * info.stepsize[1];
                z4 = info.offset[2] + (info.size[2] - 0.5) * info.stepsize[2];
                dd = fraction * (x4-x1 + y4-y1 + z4-z1) / 3;  // average
                dd = Math.min(dd, 0.45 * Math.min(x4-x1, y4-y1, z4-z1));  // failsafe
                x2 = x1 + dd, x3 = x4 - dd, y2 = y1 + dd, y3 = y4 - dd;
                traces.push({
                    type: 'scatter',
                    mode: 'lines',
                    hoverinfo: 'skip',
                    showlegend: false,
                    x: [x1, x1, x2, null, x3, x4, x4, null, x4, x4, x3, null, x2, x1, x1],
                    y: [y2, y1, y1, null, y1, y1, y2, null, y3, y4, y4, null, y4, y4, y3],
                    line: {color: info.color, width: 4}
                });
            }

            // Update figure
            let figure = {...ori_figure};
            figure.data = traces;
            return figure;
        }
        """,
            Output(self._graph.id, "figure"),
            [
                Input(self._img_traces.id, "data"),
                Input(self._indicator_traces.id, "data"),
            ],
            [
                State(self._graph.id, "figure"),
                State(self._info.id, "data"),
            ],
        )
