import os

from dash_slicer.docs import get_reference_docs, md_seperator


HERE = os.path.dirname(os.path.abspath(__file__))


def test_that_the_docs_build():
    x = get_reference_docs()
    assert "VolumeSlicer(app, vol" in x
    assert "create_overlay_data(mask" in x
    assert "performance" in x.lower()


def test_that_reference_docs_in_readme_are_up_to_date():
    filename = os.path.join(os.path.dirname(HERE), "README.md")
    assert os.path.isfile(filename)
    with open(filename, "rb") as f:
        text = f.read().decode()
    _, _, ref = text.partition(md_seperator)
    ref1 = ref.strip().replace("\r\n", "\n")
    ref2 = get_reference_docs().strip()
    assert (
        ref1 == ref2
    ), "Reference docs in readme are outdated. Run `python update_docs_in_readme.py`"
