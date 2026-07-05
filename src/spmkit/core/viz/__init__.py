"""Visualización: figuras de publicación editables y colormaps científicos."""

from spmkit.core.viz import colormaps
from spmkit.core.viz.figure import (
    Annotation,
    FigureSpec,
    render_channel,
    render_grid,
    save_figure,
    save_grid,
)
from spmkit.core.viz.forcecurve import render_force_curve, save_force_curve

__all__ = [
    "colormaps",
    "FigureSpec",
    "Annotation",
    "render_channel",
    "render_grid",
    "save_figure",
    "save_grid",
    "render_force_curve",
    "save_force_curve",
]
