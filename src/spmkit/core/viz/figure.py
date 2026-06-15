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
    colormap: str = "gold"
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


def render_channel(channel: SPMChannel, spec: FigureSpec | None = None, fig: Any = None) -> Any:
    """Construye una figura matplotlib del canal según ``spec``.

    Si se pasa ``fig`` (p.ej. la figura de un lienzo embebido) se dibuja sobre
    ella, manteniendo el vínculo figura↔lienzo (necesario para interacción).
    """
    spec = spec or FigureSpec(title=channel.name, colorbar_label=f"{channel.name} ({channel.unit})")
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    with plt.rc_context({"font.family": spec.font_family, "font.size": spec.tick_fontsize}):
        if fig is None:
            fig, ax = plt.subplots(figsize=(5, 4), dpi=spec.dpi)
        else:
            fig.clear()
            ax = fig.add_subplot(111)
        extent = (0.0, channel.x_range * 1e6, 0.0, channel.y_range * 1e6)  # µm
        im = ax.imshow(
            channel.data,
            cmap=colormaps.get_cmap(spec.colormap),
            origin="upper",
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


def render_grid(
    channels: list[SPMChannel],
    spec: FigureSpec | None = None,
    labels: list[str] | None = None,
    ncols: int | None = None,
    shared_scale: bool = True,
    fig: Any = None,
) -> Any:
    """Compone varias imágenes en un panel con **colorbar y escala compartidas**.

    Ideal para comparar 2–4 archivos lado a lado con la misma referencia de
    color (mismo gradiente) y una sola barra de escala.

    Args:
        channels: Lista de canales a comparar (2–4 típicamente).
        labels: Título de cada panel (por defecto, nombre del canal).
        ncols: Columnas de la grilla (por defecto, una fila).
        shared_scale: Si ``True``, usa el mismo ``vmin/vmax`` global en todos.
    """
    if not channels:
        raise ValueError("Se requiere al menos un canal")
    spec = spec or FigureSpec()
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    import numpy as np

    n = len(channels)
    ncols = ncols or n
    nrows = int(np.ceil(n / ncols))
    labels = labels or [c.name for c in channels]

    vmin: float | None
    vmax: float | None
    if shared_scale and spec.vmin is None and spec.vmax is None:
        allvals = np.concatenate([c.data.ravel() for c in channels])
        vmin, vmax = float(np.nanmin(allvals)), float(np.nanmax(allvals))
    else:
        vmin, vmax = spec.vmin, spec.vmax

    cmap = colormaps.get_cmap(spec.colormap)
    with plt.rc_context({"font.family": spec.font_family, "font.size": spec.tick_fontsize}):
        if fig is None:
            fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3.6 * nrows), dpi=spec.dpi)
        else:
            fig.clear()
            fig.set_size_inches(4 * ncols, 3.6 * nrows)
            axes = fig.subplots(nrows, ncols)
        axes = np.atleast_1d(axes).ravel()
        im = None
        for ax, ch, label in zip(axes, channels, labels, strict=False):
            extent = (0.0, ch.x_range * 1e6, 0.0, ch.y_range * 1e6)
            im = ax.imshow(
                ch.data,
                cmap=cmap,
                origin="upper",
                extent=extent,
                vmin=vmin,
                vmax=vmax,
                aspect="equal",
            )
            ax.set_title(label, fontsize=spec.label_fontsize)
            ax.set_xlabel(spec.xlabel, fontsize=spec.tick_fontsize)
        for ax in axes[n:]:
            ax.axis("off")
        if spec.show_scalebar:
            # Una sola barra si todos los barridos miden igual; si no, una por
            # panel (correcto por escala). Evita una escala única engañosa.
            same_size = len({round(c.x_range, 12) for c in channels}) == 1
            if same_size:
                _add_scalebar(axes[0], channels[0], spec.scalebar_color)
            else:
                for ax, ch in zip(axes[:n], channels, strict=False):
                    _add_scalebar(ax, ch, spec.scalebar_color)
        if spec.title:
            fig.suptitle(spec.title, fontsize=spec.title_fontsize)
        if spec.show_colorbar and im is not None:
            fig.subplots_adjust(right=0.88)
            cax = fig.add_axes((0.90, 0.15, 0.02, 0.7))
            fig.colorbar(im, cax=cax).set_label(spec.colorbar_label, fontsize=spec.label_fontsize)
    return fig


def save_grid(channels: list[SPMChannel], spec: FigureSpec, path: str | Path, **kw: Any) -> Path:
    """Renderiza y guarda un panel comparativo multi-imagen."""
    import matplotlib.pyplot as plt

    path = Path(path)
    fig = render_grid(channels, spec, **kw)
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
