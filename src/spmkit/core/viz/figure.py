"""Renderizado de figuras de publicación a partir de un ``FigureSpec``.

El ``FigureSpec`` es un modelo editable que describe *qué* mostrar (título,
ejes, colormap, barra de escala, anotaciones, tipografía). La GUI edita este
spec (campos de texto, dropdowns, arrastrar anotaciones) y vuelve a renderizar.
Así el "qué dibujar" vive en el core y el "cómo editarlo" en la GUI.

Requiere el extra ``viz`` (``pip install 'spmkit[viz]'``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from spmkit.core.models import SPMChannel
from spmkit.core.viz import colormaps


@dataclass
class Annotation:
    """Texto colocado sobre la figura (posición en fracción de ejes 0..1)."""

    text: str
    x: float = 0.5
    y: float = 0.9
    fontsize: float = 12.0
    color: str = "white"


@dataclass
class FigureSpec:
    """Descripción editable de una figura de imagen SPM."""

    title: str = ""
    xlabel: str = "x (µm)"
    ylabel: str = "y (µm)"
    colormap: str = "batlow"
    vmin: float | None = None
    vmax: float | None = None
    show_colorbar: bool = True
    colorbar_label: str = ""
    show_scalebar: bool = True
    scalebar_color: str = "white"
    title_fontsize: float = 14.0
    label_fontsize: float = 11.0
    tick_fontsize: float = 9.0
    font_family: str = "DejaVu Sans"
    dpi: int = 300
    annotations: list[Annotation] = field(default_factory=list)


def render_channel(channel: SPMChannel, spec: FigureSpec | None = None) -> Any:
    """Construye (sin guardar) una figura matplotlib del canal según ``spec``."""
    spec = spec or FigureSpec(title=channel.name, colorbar_label=f"{channel.name} ({channel.unit})")
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    with plt.rc_context({"font.family": spec.font_family, "font.size": spec.tick_fontsize}):
        fig, ax = plt.subplots(figsize=(5, 4), dpi=spec.dpi)
        extent = (0.0, channel.x_range * 1e6, 0.0, channel.y_range * 1e6)  # µm
        im = ax.imshow(
            channel.data,
            cmap=colormaps.get_cmap(spec.colormap),
            origin="lower",
            extent=extent,
            vmin=spec.vmin,
            vmax=spec.vmax,
            aspect="equal",
        )
        ax.set_title(spec.title, fontsize=spec.title_fontsize)
        ax.set_xlabel(spec.xlabel, fontsize=spec.label_fontsize)
        ax.set_ylabel(spec.ylabel, fontsize=spec.label_fontsize)

        if spec.show_colorbar:
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label(spec.colorbar_label, fontsize=spec.label_fontsize)

        if spec.show_scalebar:
            _add_scalebar(ax, channel, spec.scalebar_color)

        for ann in spec.annotations:
            ax.text(
                ann.x,
                ann.y,
                ann.text,
                transform=ax.transAxes,
                fontsize=ann.fontsize,
                color=ann.color,
                ha="center",
                va="center",
            )
        fig.tight_layout()
    return fig


def save_figure(channel: SPMChannel, spec: FigureSpec, path: str | Path) -> Path:
    """Renderiza y guarda la figura (formato según extensión: png/svg/pdf)."""
    import matplotlib.pyplot as plt

    path = Path(path)
    fig = render_channel(channel, spec)
    fig.savefig(path, dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _add_scalebar(ax: Any, channel: SPMChannel, color: str) -> None:
    """Añade una barra de escala física usando matplotlib-scalebar si existe."""
    try:
        from matplotlib_scalebar.scalebar import ScaleBar
    except ImportError:  # pragma: no cover - scalebar opcional
        return
    # El eje ya está en µm (vía extent); cada unidad de dato = 1 µm.
    bar = ScaleBar(1.0, units="um", color=color, box_alpha=0, location="lower right")
    ax.add_artist(bar)
