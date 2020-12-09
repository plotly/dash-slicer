# The docstring below is used as part of the reference docs. It describes
# the parts that cannot be described well via the properties and methods.

"""

### Reacting to slicer state

It is possible to get notified of updates to slicer position and
view ranges. To get this for all slicers with a specific scene_id, create
a [pattern matching input](https://dash.plotly.com/pattern-matching-callbacks)
like this:
```py
Input({"scene": scene_id, "context": ALL, "name": "state"})
```

See the `state` property for details.


### Setting slicer positions

To programatically set the position of the slicer, create a `dcc.Store` with
a dictionary-id that has the following fields:

* 'context': a unique name for this store.
* 'scene': the scene_id of the slicer objects to set the position for.
* 'name': 'setpos'

The value in the store must be an 3-element tuple (x, y, z) in scene coordinates.
To apply the position for one dimension only, use e.g `(None, None, x)`.


### Performance tips

There tends to be a lot of interaction in an application that contains
slicer objects. To realize a smooth user experience, performance matters.
Here are some tips to help with that:

* Most importantly, when running the server in debug mode, consider setting
  `dev_tools_props_check=False`.
* Also consider creating the `Dash` application with `update_title=None`.
* Setting `reverse_y` to False negatively affects performance. This will be
  fixed in a future version of Plotly/Dash.
* For a smooth experience, avoid triggering unnecessary figure updates.
* When adding a callback that uses the slicer position, use the (rate limited)
  `state` store rather than the slider value.

"""

import numpy as np
import plotly.graph_objects
import dash
from dash.dependencies import Input, Output, State, ALL
from dash_core_components import Graph, Slider, Store, Interval

from .utils import img_array_to_uri, get_thumbnail_size, shape3d_to_size2d


# The default colors to use for indicators and overlays
discrete_colors = plotly.colors.qualitative.D3

_assigned_scene_ids = {}  # id(volume) -> str


class VolumeSlicer:
    """A slicer object to show 3D image data in Dash. Upon
    instantiation one can provide the following parameters:

    * `app` (`dash.Dash`): the Dash application instance.
    * `volume` (`ndarray`): the 3D numpy array to slice through. The dimensions
      are assumed to be in zyx order. If this is not the case, you can
      use `np.swapaxes` to make it so.
    * `spacing` (tuple of `float`): the distance between voxels for each
      dimension (zyx). The spacing and origin are applied to make the slice
      drawn in "scene space" rather than "voxel space".
    * `origin` (tuple of `float`): the offset for each dimension (zyx).
    * `axis` (`int`): the dimension to slice in. Default 0.
    * `reverse_y` (`bool`): whether to reverse the y-axis, so that the origin of
      the slice is in the top-left, rather than bottom-left. Default True.
      Note: setting this to False affects performance, see #12. This has been
      fixed, but the fix has not yet been released with Dash.
    * `scene_id` (`str`): the scene that this slicer is part of. Slicers
      that have the same scene-id show each-other's positions with
      line indicators. By default this is derived from `id(volume)`.
    * `color` (`str`): the color for this slicer. By default the color
      is a shade of blue, orange, or green, depending on the axis. Set
      to empty string to prevent drawing indicators for this slicer.
    * `thumbnail` (`int` or `bool`): the preferred size of low-resolution data
      to be uploaded to the client. If `False`, the full-resolution data are
      uploaded client-side. If `True` (default), a default value of 32 is used.

    Note that this is not a Dash Component. The components that make
    up the slicer (and which must be present in the layout) are:
    `slicer.graph`, `slicer.slider`, and `slicer.stores`.
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
        thumbnail=True,
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

        # Check and store thumbnail
        if not (isinstance(thumbnail, (int, bool))):
            raise ValueError("thumbnail must be a boolean or an integer.")
        if thumbnail is False:
            self._thumbnail = False
        elif thumbnail is None or thumbnail is True:
            self._thumbnail = 32  # default size
        else:
            thumbnail = int(thumbnail)
            if thumbnail >= np.max(volume.shape[:3]):
                self._thumbnail = False  # dont go larger than image size
            elif thumbnail <= 0:
                self._thumbnail = False  # consider 0 and -1 the same as False
            else:
                self._thumbnail = thumbnail

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
        if thumbnail:
            self._create_server_callbacks()
        self._create_client_callbacks()

    # Note(AK): we could make some stores public, but let's do this only when actual use-cases arise?

    @property
    def scene_id(self) -> str:
        """The id of the "virtual scene" for this slicer. Slicers that have
        the same scene_id show each-other's positions.
        """
        return self._scene_id

    @property
    def axis(self) -> int:
        """The axis to slice."""
        return self._axis

    @property
    def nslices(self) -> int:
        """The number of slices for this slicer."""
        return self._volume.shape[self._axis]

    @property
    def graph(self):
        """The `dcc.Graph` for this slicer. Use `graph.figure` to access the
        Plotly Figure object.
        """
        return self._graph

    @property
    def slider(self):
        """The `dcc.Slider` to change the index for this slicer. If you
        don't want to use the slider, wrap it in a div with style
        `display: none`.
        """
        return self._slider

    @property
    def stores(self):
        """A list of `dcc.Store` objects that the slicer needs to work.
        These must be added to the app layout.
        """
        return self._stores

    @property
    def state(self):
        """A `dcc.Store` representing the current state of the slicer (present
        in slicer.stores). Its data is a dict with the fields:

        * "index": the integer slice index.
        * "index_changed": a bool indicating whether the index changed since last time.
        * "xrange": the view range (2 floats) in the x-dimension (2D).
        * "yrange": the view range (2 floats) in the y-dimension (2D).
        * "zpos": the float position aling the axis, in scene coordinates.
        * "axis": the axis (int) for this slicer.
        * "color": the color (str) for this slicer.

        The id of the store is a dictionary so it can be used in a
        pattern matching Input. Its field are: context, scene, name.
        Where scene is the scene_id and name is "state".
        """
        return self._state

    @property
    def overlay_data(self):
        """A `dcc.Store` containing the overlay data. The form of this
        data is considered an implementation detail; users are expected to use
        `create_overlay_data` to create it.
        """
        return self._overlay_data

    def create_overlay_data(self, mask, color=None):
        """Given a 3D mask array and an index, create an object that
        can be used as output for `slicer.overlay_data`. The color
        can be a hex color or an rgb/rgba tuple. Alternatively, color
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

        # Prep low-res slices. The get_thumbnail_size() is a bit like
        # a simulation to get the low-res size.
        if not self._thumbnail:
            thumbnail_size = None
            info["thumbnail_size"] = info["size"]
        else:
            thumbnail_size = self._thumbnail
            info["thumbnail_size"] = get_thumbnail_size(
                info["size"][:2], thumbnail_size
            )
        thumbnails = [
            img_array_to_uri(self._slice(i), thumbnail_size)
            for i in range(info["size"][2])
        ]

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
            autorange=True,
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

        # Create a slider object that the user can put in the layout (or not).
        # Note that the tooltip introduces a measurable performance penalty,
        # so maybe we can display it in a different way?
        self._slider = Slider(
            id=self._subid("slider"),
            min=0,
            max=info["size"][2] - 1,
            step=1,
            value=info["size"][2] // 2,
            updatemode="drag",
            tooltip={"always_visible": False, "placement": "left"},
        )

        # Create the stores that we need (these must be present in the layout)

        # A dict of static info for this slicer
        self._info = Store(id=self._subid("info"), data=info)

        # A list of low-res slices, or the full-res data (encoded as base64-png)
        self._thumbs_data = Store(id=self._subid("thumbs"), data=thumbnails)

        # A list of mask slices (encoded as base64-png or null)
        self._overlay_data = Store(id=self._subid("overlay"), data=[])

        # Slice data provided by the server
        self._server_data = Store(
            id=self._subid("server-data"), data={"index": -1, "slice": None}
        )

        # Store image traces for the slicer.
        self._img_traces = Store(id=self._subid("img-traces"), data=[])

        # Store indicator traces for the slicer.
        self._indicator_traces = Store(id=self._subid("indicator-traces"), data=[])

        # A timer to apply a rate-limit between slider.value and index.data
        self._timer = Interval(id=self._subid("timer"), interval=100, disabled=True)

        # The (public) state of the slicer. This value is rate-limited. Initially null.
        self._state = Store(id=self._subid("state", True), data=None)

        # Signal to set the position of other slicers with the same scene_id.
        self._setpos = Store(id=self._subid("setpos", True), data=None)

        self._stores = [
            self._info,
            self._thumbs_data,
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
            if state is None or not state["index_changed"]:
                return dash.no_update
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
        function update_index_rate_limiting(index, relayoutData, n_intervals, info, figure) {

            if (!window._slicer_{{ID}}) window._slicer_{{ID}} = {};
            let private_state = window._slicer_{{ID}};
            let now = window.performance.now();

            // Get whether the slider was moved
            let slider_value_changed = false;
            let graph_layout_changed = false;
            let timer_ticked = false;
            for (let trigger of dash_clientside.callback_context.triggered) {
                if (trigger.prop_id.indexOf('slider') >= 0) slider_value_changed = true;
                if (trigger.prop_id.indexOf('graph') >= 0) graph_layout_changed = true;
                if (trigger.prop_id.indexOf('timer') >= 0) timer_ticked = true;
            }

            // Calculate view range based on the volume
            let xrangeVol = [
                info.offset[0] - 0.5 * info.stepsize[0],
                info.offset[0] + (info.size[0] - 0.5) * info.stepsize[0]
            ];
            let yrangeVol = [
                info.offset[1] - 0.5 * info.stepsize[1],
                info.offset[1] + (info.size[1] - 0.5) * info.stepsize[1]
            ];

            // Get view range from the figure. We make range[0] < range[1]
            let xrangeFig = figure.layout.xaxis.range
            let yrangeFig = figure.layout.yaxis.range;
            xrangeFig = [Math.min(xrangeFig[0], xrangeFig[1]), Math.max(xrangeFig[0], xrangeFig[1])];
            yrangeFig = [Math.min(yrangeFig[0], yrangeFig[1]), Math.max(yrangeFig[0], yrangeFig[1])];

            // Add offset to avoid the corner-indicators for THIS slicer to only be half-visible
            let plotSize = [400, 400];  // This estimate results in ok results
            let graphDiv = document.getElementById('{{ID}}-graph');
            let plotDiv = graphDiv.getElementsByClassName('js-plotly-plot')[0];
            if (plotDiv && plotDiv._fullLayout)
                plotSize = [plotDiv._fullLayout.width, plotDiv._fullLayout.height];
            xrangeFig[0] += 2 * (xrangeFig[1] - xrangeFig[0]) / plotSize[0];
            xrangeFig[1] -= 2 * (xrangeFig[1] - xrangeFig[0]) / plotSize[0];
            yrangeFig[0] += 2 * (yrangeFig[1] - yrangeFig[0]) / plotSize[1];
            yrangeFig[1] -= 2 * (yrangeFig[1] - yrangeFig[0]) / plotSize[1];

            // Combine the ranges
            let xrange = [Math.max(xrangeVol[0], xrangeFig[0]), Math.min(xrangeVol[1], xrangeFig[1])];
            let yrange = [Math.max(yrangeVol[0], yrangeFig[0]), Math.min(yrangeVol[1], yrangeFig[1])];

            // Initialize return values
            let new_state = dash_clientside.no_update;
            let disable_timer = false;

            // If the slider moved, remember the time when this happened
            private_state.new_time = private_state.new_time || 0;


            if (slider_value_changed) {
                private_state.new_time = now;
                private_state.timeout = 200;
            } else if (graph_layout_changed) {
                private_state.new_time = now;
                private_state.timeout = 400;  // need longer timeout for smooth scroll zoom
            } else if (!n_intervals) {
                private_state.new_time = now;
                private_state.timeout = 100;
            }

            // We can either update the rate-limited index timeout ms after
            // the real index changed, or timeout ms after it stopped
            // changing. The former makes the indicators come along while
            // dragging the slider, the latter is better for a smooth
            // experience, and the timeout can be set much lower.
            if (private_state.timeout && timer_ticked && now - private_state.new_time >= private_state.timeout) {
                private_state.timeout = 0;
                disable_timer = true;
                new_state = {
                    index: index,
                    index_changed: false,
                    xrange: xrange,
                    yrange: yrange,
                    zpos: info.offset[2] + index * info.stepsize[2],
                    axis: info.axis,
                    color: info.color,
                };
                if (index != private_state.index) {
                    private_state.index = index;
                    new_state.index_changed = true;
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
            [
                Input(self._slider.id, "value"),
                Input(self._graph.id, "relayoutData"),
                Input(self._timer.id, "n_intervals"),
            ],
            [
                State(self._info.id, "data"),
                State(self._graph.id, "figure"),
            ],
        )

        # ----------------------------------------------------------------------
        # Callback that creates a list of image traces (slice and overlay).

        app.clientside_callback(
            """
        function update_image_traces(index, server_data, overlays, thumbnails, info, current_traces) {

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

            // Use full data, or use thumbnails
            if (index == server_data.index) {
                slice_trace.source = server_data.slice;
            } else {
                slice_trace.source = thumbnails[index];
                // Scale the image to take the exact same space as the full-res
                // version. Note that depending on how the low-res data is
                // created, the pixel centers may not be correctly aligned.
                slice_trace.dx *= info.size[0] / info.thumbnail_size[0];
                slice_trace.dy *= info.size[1] / info.thumbnail_size[1];
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
                State(self._thumbs_data.id, "data"),
                State(self._info.id, "data"),
                State(self._img_traces.id, "data"),
            ],
        )

        # ----------------------------------------------------------------------
        # Callback to create scatter traces from the positions of other slicers.

        app.clientside_callback(
            """
        function update_indicator_traces(states, info, thisState) {
            let traces = [];

            for (let state of states) {
                if (!state) continue;
                let zpos = [state.zpos, state.zpos];
                let trace = null;
                if        (info.axis == 0 && state.axis == 1) {
                    trace = {x: state.xrange, y: zpos};
                } else if (info.axis == 0 && state.axis == 2) {
                    trace = {x: zpos, y: state.xrange};
                } else if (info.axis == 1 && state.axis == 2) {
                    trace = {x: zpos, y: state.yrange};
                } else if (info.axis == 1 && state.axis == 0) {
                    trace = {x: state.xrange, y: zpos};
                } else if (info.axis == 2 && state.axis == 0) {
                    trace = {x: state.yrange, y: zpos};
                } else if (info.axis == 2 && state.axis == 1) {
                    trace = {x: zpos, y: state.yrange};
                }
                if (trace) {
                    trace.line = {color: state.color, width: 1};
                    traces.push(trace);
                }
            }

            // Show our own color around the image, but only if there are other
            // slicers with the same scene id, on a different axis. We do some
            // math to make sure that these indicators are the same size (in
            // scene coordinates) for all slicers of the same data.
            if (thisState && info.color && traces.length) {
                let fraction = 0.1;
                let lengthx = info.size[0] * info.stepsize[0];
                let lengthy = info.size[1] * info.stepsize[1];
                let lengthz = info.size[2] * info.stepsize[2];
                let dd = fraction * (lengthx + lengthy + lengthz) / 3;  // average
                dd = Math.min(dd, 0.45 * Math.min(lengthx, lengthy, lengthz));  // failsafe
                let x1 = thisState.xrange[0];
                let x2 = thisState.xrange[0] + dd;
                let x3 = thisState.xrange[1] - dd;
                let x4 = thisState.xrange[1];
                let y1 = thisState.yrange[0];
                let y2 = thisState.yrange[0] + dd;
                let y3 = thisState.yrange[1] - dd;
                let y4 = thisState.yrange[1];
                traces.push({
                    x: [x1, x1, x2, null, x3, x4, x4, null, x4, x4, x3, null, x2, x1, x1],
                    y: [y2, y1, y1, null, y1, y1, y2, null, y3, y4, y4, null, y4, y4, y3],
                    line: {color: info.color, width: 4}
                });
            }

            // Post-process the traces we created above
            for (let trace of traces) {
                trace.type = 'scatter';
                trace.mode = 'lines';
                trace.hoverinfo = 'skip';
                trace.showlegend = false;
            }
            if (thisState) {
                return traces;
            } else {
                return dash_clientside.no_update;
            }
        }
        """,
            Output(self._indicator_traces.id, "data"),
            [Input({"scene": self._scene_id, "context": ALL, "name": "state"}, "data")],
            [
                State(self._info.id, "data"),
                State(self._state.id, "data"),
            ],
            prevent_initial_call=True,
        )

        # ----------------------------------------------------------------------
        # Callback that composes a figure from multiple trace sources.

        app.clientside_callback(
            """
        function update_figure(img_traces, indicators, info, ori_figure) {
            // Collect traces
            let traces = [];
            for (let trace of img_traces) { traces.push(trace); }
            for (let trace of indicators) { if (trace.line.color) traces.push(trace); }
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
            [State(self._info.id, "data"), State(self._graph.id, "figure")],
        )
