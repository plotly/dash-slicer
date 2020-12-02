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
