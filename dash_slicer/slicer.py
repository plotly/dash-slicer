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

# ### Developer notes ###
#
# ## Linking of slicers
#
# The approach that has been taken is to let users create a VolumeSlicer
# for each view to be created. To still allow different slicers to be
# aware of each-other, we gratefully make use of dict-id's and pattern
# matching inputs. This also adds a lot of flexibility to the number
# of views that a user wants to create. To prevent all slicers in an
# application to be linked, we introduce the concept of a scene_id,
# which is simply a field in the dict ids to filter by.
#
# ## Synchronizing slicer figures
#
# It's tempting to let changes made in one slicer (e.g. changing the
# slice index) to directly take effect in the other slicers. However,
# this causes a lot of figure updates, which quickly makes the
# interaction jerky. Instead, a rate-limited `state` is created, for
# other slicers (and application code) to react to. This helps allocate
# most CPU cycles for the interaction of the current slicer, creating
# a smooth experience. For similar reasons, synchronizing e.g. view
# ranges between multiple slicers would be challenging.
#
# ## The slider.value is part of the flow
#
# The slider can be used to set the index, but we also want to allow
# setting the index from the outside. To avoid a circular flow, the
# slider.value *is* the reference index. Therefore the slider must be
# present in the layout, and must be hidden (not omitted) if the user
# does not want it. It may be possible to work around this, but right
# now this seems by far the easiest solution :)


import numpy as np
import plotly.graph_objects
import dash
from dash.dependencies import Input, Output, State, ALL
from dash_core_components import Graph, Slider, Store, Interval

from .utils import (
    discrete_colors,
    img_array_to_uri,
    get_thumbnail_size,
    shape3d_to_size2d,
    mask_to_coloured_slices,
)


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
    * `clim` (tuple of `float`): the (initial) contrast limits. Default the min
      and max of the volume.
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
        clim=None,
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

        # Check and store contrast limits
        if clim is None:
            self._initial_clim = self._volume.min(), self._volume.max()
        elif isinstance(clim, (tuple, list)) and len(clim) == 2:
            self._initial_clim = float(clim[0]), float(clim[1])
        else:
            raise TypeError("The clim must be None or a 2-tuple of floats.")

        # Check and store thumbnail
        if not (isinstance(thumbnail, (int, bool))):
            raise TypeError("thumbnail must be a boolean or an integer.")
        if not thumbnail:
            self._thumbnail_param = None
        elif thumbnail is True:
            self._thumbnail_param = 32  # default size
        else:
            thumbnail = int(thumbnail)
            if thumbnail >= np.max(volume.shape[:3]):
                self._thumbnail_param = None  # dont go larger than image size
            elif thumbnail <= 0:
                self._thumbnail_param = None  # consider 0 and -1 the same as False
            else:
                self._thumbnail_param = thumbnail

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
            "infoid": np.random.randint(1, 9999999),
        }

        # Also store thumbnail size. The get_thumbnail_size() is a bit like
        # a simulation to get the low-res size.
        if self._thumbnail_param is None:
            self._slice_info["thumbnail_size"] = self._slice_info["size"][:2]
        else:
            self._slice_info["thumbnail_size"] = get_thumbnail_size(
                self._slice_info["size"][:2], self._thumbnail_param
            )

        # Build the slicer
        self._create_dash_components()
        self._create_server_callbacks()
        self._create_client_callbacks()

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
        These must be added to the app layout. Note that public stores
        like `state` and `extra_traces` are also present in this list.
        """
        return self._stores

    @property
    def state(self):
        """A `dcc.Store` representing the current state of the slicer (present
        in slicer.stores). This store is intended for use as State or Input.
        Its data is a dict with the fields:

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
    def clim(self):
        """A `dcc.Store` to be used as Output, representing the contrast
        limits as a 2-element tuple. This value should probably not be
        changed too often (e.g. on slider drag) because the thumbnail
        data is recreated on each change.
        """
        return self._clim

    @property
    def extra_traces(self):
        """A `dcc.Store` to be used as an Output to define additional
        traces to be shown in this slicer. The data must be a list of
        dictionaries, with each dict representing a raw trace object.
        """
        return self._extra_traces

    @property
    def overlay_data(self):
        """A `dcc.Store` to be used an Output for the overlay data. The
        form of this data is considered an implementation detail; users
        are expected to use `create_overlay_data` to create it.
        """
        return self._overlay_data

    def create_overlay_data(self, mask, color=None):
        """Given a 3D mask array, create an object that can be used as
        output for `slicer.overlay_data`. Set mask to `None` to clear the mask.
        The color can be a hex color or an rgb/rgba tuple. Alternatively,
        color can be a list of such colors, defining a colormap.
        """
        if mask is None:
            return [None for index in range(self.nslices)]  # A reset
        elif mask.shape != self._volume.shape:
            raise ValueError(
                f"Overlay must has shape {mask.shape}, but expected {self._volume.shape}"
            )
        return mask_to_coloured_slices(mask, self._axis, color)

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

    def _slice(self, index, clim):
        """Sample a slice from the volume."""
        # Sample from the volume
        indices = [slice(None), slice(None), slice(None)]
        indices[self._axis] = index
        im = self._volume[tuple(indices)].astype(np.float32)
        # Apply contrast limits
        clim = min(clim), max(clim)
        im = (im - clim[0]) * (255 / (clim[1] - clim[0]))
        im[im < 0] = 0
        im[im > 255] = 255
        return im.astype(np.uint8)

    def _create_dash_components(self):
        """Create the graph, slider, figure, etc."""
        info = self._slice_info

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

        # A tuple representing the contrast limits
        self._clim = Store(id=self._subid("clim"), data=self._initial_clim)

        # A list of thumbnails (low-res, or the full-re, encoded as base64-png)
        self._thumbs_data = Store(id=self._subid("thumbs"), data=[])

        # A list of mask slices (encoded as base64-png or null)
        self._overlay_data = Store(id=self._subid("overlay"), data=[])

        # Slice data provided by the server
        self._server_data = Store(
            id=self._subid("server-data"), data={"index": -1, "slice": None}
        )

        # Store image traces to show in the figure
        self._img_traces = Store(id=self._subid("img-traces"), data=[])

        # Store indicator traces to show in the figure
        self._indicator_traces = Store(id=self._subid("indicator-traces"), data=[])

        # Store more (user-defined) traces to show in the figure
        self._extra_traces = Store(id=self._subid("extra-traces"), data=[])

        # A timer to apply a rate-limit between slider.value and index.data
        self._timer = Interval(id=self._subid("timer"), interval=100, disabled=True)

        # The (public) state of the slicer. This value is rate-limited. Initially null.
        self._state = Store(id=self._subid("state", True), data=None)

        # Signal to set the position of other slicers with the same scene_id.
        self._setpos = Store(id=self._subid("setpos", True), data=None)

        self._stores = [
            self._info,
            self._clim,
            self._thumbs_data,
            self._overlay_data,
            self._server_data,
            self._img_traces,
            self._indicator_traces,
            self._extra_traces,
            self._timer,
            self._state,
            self._setpos,
        ]

    def _create_server_callbacks(self):
        """Create the callbacks that run server-side."""
        app = self._app

        @app.callback(
            Output(self._thumbs_data.id, "data"),
            [Input(self._clim.id, "data")],
        )
        def upload_thumbnails(clim):
            return [
                img_array_to_uri(self._slice(i, clim), self._thumbnail_param)
                for i in range(self.nslices)
            ]

        if self._thumbnail_param is not None:
            # The callback to push full-res slices to the client is only needed
            # if the thumbnails are not already full-res.

            @app.callback(
                Output(self._server_data.id, "data"),
                [Input(self._state.id, "data"), Input(self._clim.id, "data")],
            )
            def upload_requested_slice(state, clim):
                if state is None or not state["index_changed"]:
                    return dash.no_update
                index = state["index"]
                slice = img_array_to_uri(self._slice(index, clim))
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
        #             ------------------------/          \
        #                                                 \
        #        state (external)  -->  indicator_traces -- ----->  figure
        #                                                 /
        #                                         extra_traces
        #
        # This figure is incomplete, for the sake of keeping it
        # relatively simple. E.g. the thumbnail data is also an input
        # for the callback that generates the image traces. And the
        # clim store is an input for the callbacks that produce
        # server_data and thumbnail data.

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
        # Callback to rate-limit the state (using a timer/interval).
        # This callback has as input anything that defines the state. The callback
        # checks what was changed, sets a timeout, and enables the timer.

        app.clientside_callback(
            """
        function update_rate_limiting_info(index, relayoutData, n_intervals) {

            if (!window._slicer_{{ID}}) window._slicer_{{ID}} = {};
            let private_state = window._slicer_{{ID}};
            let now = window.performance.now();

            // Get whether the slider was moved, layout was changed, or timer ticked
            let slider_value_changed = false;
            let graph_layout_changed = false;
            let timer_ticked = false;
            for (let trigger of dash_clientside.callback_context.triggered) {
                if (trigger.prop_id.indexOf('slider') >= 0) slider_value_changed = true;
                if (trigger.prop_id.indexOf('timer') >= 0) timer_ticked = true;
                if (trigger.prop_id.indexOf('graph') >= 0) {
                    for (let key in relayoutData) {
                        if (key.startsWith("xaxis.range") || key.startsWith("yaxis.range")) {
                            graph_layout_changed = true;
                        }
                    }
                }
            }

            // Set timeout and whether to disable the timer
            let disable_timer = false;
            if (slider_value_changed) {
                private_state.timeout = now + 200;
            } else if (graph_layout_changed) {
                private_state.timeout = now + 400;  // need longer timeout for smooth scroll zoom
            } else if (!n_intervals) {
                private_state.timeout = now + 100;  // initialize
            } else if (!private_state.timeout) {
                disable_timer = true;
            }

            return disable_timer;
        }
        """.replace(
                "{{ID}}", self._context_id
            ),
            Output(self._timer.id, "disabled"),
            [
                Input(self._slider.id, "value"),
                Input(self._graph.id, "relayoutData"),
                Input(self._timer.id, "n_intervals"),
            ],
            prevent_initial_call=True,
        )

        # ----------------------------------------------------------------------
        # Callback to produce the (rate-limited) state.
        # Note how this callback only has the interval as input. This breaks
        # any loops in applications that want to both get and set the slicer
        # position.

        app.clientside_callback(
            """
        function update_state(n_intervals, index, info, figure) {

            if (!window._slicer_{{ID}}) window._slicer_{{ID}} = {};
            let private_state = window._slicer_{{ID}};
            let now = window.performance.now();

            // Ready to apply and stop the timer, or return early?
            if (!(private_state.timeout && now >= private_state.timeout)) {
                return dash_clientside.no_update;
            }
            // Give the plot time to settle the initial axis ranges
            if (n_intervals < 5) {
                return dash_clientside.no_update;
            }

            // Disable the timer
            private_state.timeout = 0;

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

            // Create new state
            let new_state = {
                index: index,
                index_changed: false,
                xrange: xrange,
                yrange: yrange,
                zpos: info.offset[2] + index * info.stepsize[2],
                axis: info.axis,
                color: info.color,
            };
            if (index != private_state.last_index || info.infoid != private_state.infoid) {
                private_state.last_index = index;
                new_state.index_changed = true;
            }
            private_state.infoid = info.infoid;  // infoid changes on hot reload
            return new_state;
        }
        """.replace(
                "{{ID}}", self._context_id
            ),
            Output(self._state.id, "data"),
            [
                Input(self._timer.id, "n_intervals"),
            ],
            [
                State(self._slider.id, "value"),
                State(self._info.id, "data"),
                State(self._graph.id, "figure"),
            ],
            prevent_initial_call=True,
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
                Input(self._thumbs_data.id, "data"),
            ],
            [
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
        function update_figure(img_traces, indicator_traces, extra_traces, info, ori_figure) {
            // Collect traces
            let traces = [];
            for (let trace of img_traces) { traces.push(trace); }
            for (let trace of extra_traces) { traces.push(trace); }
            for (let trace of indicator_traces) { if (trace.line.color) traces.push(trace); }
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
                Input(self._extra_traces.id, "data"),
            ],
            [State(self._info.id, "data"), State(self._graph.id, "figure")],
        )
