![CI](https://github.com/pygfx/wgpu-py/workflows/CI/badge.svg)

# dash_slicer

A volume slicer for Dash


## Status

This work is marked as alpha - some essential features are still in
development, and some parts of the API may change in future releases.


## Installation

```
$ pip install dash-slicer
```

Dash-slicer depends on Python 3.6+ plus some [dependencies](requirements.txt).


## Usage example

```py
import dash
import dash_html_components as html
from dash_slicer import VolumeSlicer
import imageio

app = dash.Dash(__name__)

vol = imageio.volread("imageio:stent.npz")
slicer = VolumeSlicer(app, vol)
app.layout = html.Div([slicer.graph, slicer.slider, *slicer.stores])

if __name__ == "__main__":
    app.run_server()
```


## License

This code is distributed under MIT license.


## Developers


* Make sure that you have Python with the appropriate dependencies installed, e.g. via `venv`.
* Run `pip install -e .` to do an in-place install of the package.
* Run the examples using e.g. `python examples/slicer_with_1_view.py`

* Use `black .` to autoformat.
* Use `flake8 .` to lint.
* Use `pytest .` to run the tests.

On every PR, an app with the same name as your branch is deployed to the Dash
playground instance so that you can change whether your changes did not break
the package.


## Reference

### The VolumeSlicer class

**class `VolumeSlicer(app, volume, *, spacing=None, origin=None, axis=0, reverse_y=True, scene_id=None, color=None, thumbnail=True)`**

A slicer object to show 3D image data in Dash. Upon
instantiation one can provide the following parameters:

* `app` (`dash.Dash`): the Dash application instance.
* `volume` (`ndarray`): the 3D numpy array to slice through. The dimensions
  are assumed to be in zyx order. If this is not the case, you can
  use ``np.swapaxes`` to make it so.
* `spacing` (tuple of `float`): The distance between voxels for each
  dimension (zyx).The spacing and origin are applied to make the slice
  drawn in "scene space" rather than "voxel space".
* `origin` (tuple of `float`): The offset for each dimension (zyx).
* `axis` (`int`): the dimension to slice in. Default 0.
* `reverse_y` (`bool`): Whether to reverse the y-axis, so that the origin of
  the slice is in the top-left, rather than bottom-left. Default True.
  Note: setting this to False affects performance, see #12.
* `scene_id` (`str`): the scene that this slicer is part of. Slicers
  that have the same scene-id show each-other's positions with
  line indicators. By default this is derived from ``id(volume)``.
* `color` (`str`): the color for this slicer. By default the color is
  red, green, or blue, depending on the axis. Set to empty string
  for "no color".
* thumbnail (int or bool): linear size of low-resolution data to be
  uploaded to the client. If ``False``, the full-resolution data are
  uploaded client-side. If ``True`` (default), a default value of 32 is
  used.

Note that this is not a Dash component. The components that make
up the slicer (and which must be present in the layout) are:
`slicer.graph`, `slicer.slider`, and `slicer.stores`.


**method `VolumeSlicer.create_overlay_data(mask, color=None)`**

Given a 3D mask array and an index, create an object that
can be used as output for ``slicer.overlay_data``. The color
can be a hex color or an rgb/rgba tuple. Alternatively, color
can be a list of such colors, defining a colormap.


**property `VolumeSlicer.axis`**: The axis at which the slicer is slicing.

**property `VolumeSlicer.graph`**: The dcc.Graph for this slicer. Use ``graph.figure`` to access the
Plotly Figure object.


**property `VolumeSlicer.nslices`**: The number of slices for this slicer.

**property `VolumeSlicer.overlay_data`**: A dcc.Store containing the overlay data. The form of this
data is considered an implementation detail; users are expected to use
``create_overlay_data`` to create it.


**property `VolumeSlicer.scene_id`** str: The id of the "virtual scene" for this slicer. Slicers that have
the same scene_id show each-other's positions.


**property `VolumeSlicer.slider`**: The `dcc.Slider` to change the index for this slicer. If you
don't want to use the slider, wrap it in a div with style
``display: none``.


**property `VolumeSlicer.state`**: A dcc.Store representing the current state of the slicer (present
in slicer.stores). Its data is a dict with the fields: index (int),
index_changed (bool), xrange (2 floats), yrange (2 floats),
zpos (float), axis (int), color (str).

Its id is a dictionary so it can be used in a pattern matching Input.
Fields: context, scene, name. Where scene is the scene_id and name is "state".


**property `VolumeSlicer.stores`**: A list of dcc.Store objects that the slicer needs to work.
These must be added to the app layout.




### Reacting to slicer state

It is possible to get notified of updates to slicer position and
view ranges. To get this for all slicers with a specific scene_id, create
a pattern matching input like this:
```py
Input({"scene": scene_id, "context": ALL, "name": "state"})
```

These state values are objects with fields:

* "index": the integer slice index.
* "index_changed": a bool indicating whether the index changed since last time.
* "xrange": the view range (2 floats) in the x-dimension (2D).
* "yrange": the view range (2 floats) in the y-dimension (2D).
* "zpos": the float position aling the axis, in scene coordinates.
* "axis": the axis (int) for this slicer.
* "color": the color (str) for this slicer.


### Setting slicer positions

To programatically set the position of the slicer, create a `dcc.Store` with
a dictionary-id that has the following fields:

* 'context': a unique name for this store.
* 'scene': the scene_id of the slicer objects to set the position for.
* 'name': 'setpos'

The value in the store must be an 3-element tuple (x, y, z) in scene coordinates.
To apply the position for one dimension only, use e.g ``(None, None, x)``.


### Performance tips

* Most importantly, when running the server in debug mode, consider setting
  `dev_tools_props_check=False`.
* Also consider creating the `Dash` application with `update_title=None`.
* Setting `reverse_y` to False negatively affects performance. This will be
  fixed in a future version of Plotly/Dash.
* For a smooth experience, avoid triggering unnecessary figure updates.
* When adding a callback that uses the slicer position, use the (rate limited)
  `state` store rather than the slider value.

