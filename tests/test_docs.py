import os

from dash_slicer.docs import get_reference_docs


HERE = os.path.dirname(os.path.abspath(__file__))


def test_that_the_docs_build():
    x = get_reference_docs()
    assert "VolumeSlicer(app, vol" in x
    assert "create_overlay_data(mask" in x
    assert "performance" in x.lower()


def test_that_docs_are_up_to_date():
    filename = os.path.join(os.path.dirname(HERE), "README.md")
    assert os.path.isfile(filename)
    with open(filename, "rt", encoding="utf-8") as f:
        text = f.read()
    _, _, ref = text.partition("## Reference")
    ref1 = ref.strip()
    ref2 = get_reference_docs().strip()
    assert (
        ref1 == ref2
    ), "Reference docs in readme are outdated. Run `python dash_slicer/docs.py`"
