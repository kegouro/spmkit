"""Tests del render de anotaciones personalizables de figura."""

from __future__ import annotations

import pytest

pytest.importorskip("matplotlib")

from spmkit.core.viz.figure import Annotation, render_annotation  # noqa: E402


def test_annotation_all_properties_render() -> None:
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ann = Annotation(
        text="línea1\nlínea2",
        x=0.3,
        y=0.4,
        fontsize=18,
        color="#ff0000",
        ha="left",
        va="top",
        multialignment="right",
        weight="bold",
        style="italic",
        linespacing=1.6,
        rotation=30,
        bg_color="#0000ff",
        bg_alpha=0.5,
        bg_edge="#00ff00",
    )
    artist = render_annotation(ax, ann)
    assert artist.get_text() == "línea1\nlínea2"
    assert artist.get_fontsize() == 18
    assert artist.get_color() == "#ff0000"
    assert artist.get_ha() == "left"
    assert artist.get_rotation() == 30
    assert artist.get_bbox_patch() is not None  # tiene fondo
    plt.close(fig)


def test_annotation_default_has_no_background() -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    artist = render_annotation(ax, Annotation(text="x"))
    assert artist.get_bbox_patch() is None
    plt.close(fig)
