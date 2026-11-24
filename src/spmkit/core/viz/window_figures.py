"""One local PNG per acquired curve, using the windows and decisions already reviewed."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import shorten
from uuid import uuid4

import numpy as np
from matplotlib.artist import Artist
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from spmkit.core.adhesion_review import AdhesionMap, PullOff, export_review, read_for_review
from spmkit.core.analysis.force_windows import AutoWindow
from spmkit.core.force_window_batch import WindowBatch, WindowRow
from spmkit.core.models import ForceCurve

_BRANCHES = {"extend": ("Aproximación", "#176180", "-"), "retract": ("Retracción", "#894628", "--")}
_HIGHLIGHT = "#007763"
_MARK = "#a33b26"


@dataclass(frozen=True)
class CurvePanel:
    index: int
    windows: tuple[AutoWindow, ...] = ()
    adhesion: PullOff | None = None
    note: str = ""


@dataclass(frozen=True)
class FigureMap:
    path: Path
    digest: str
    panels: list[CurvePanel]


def _maps(batch: WindowBatch | Sequence[AdhesionMap]) -> list[FigureMap]:
    if not isinstance(batch, WindowBatch):
        return [
            FigureMap(
                m.path,
                m.digest,
                [CurvePanel(r.index, adhesion=r, note=r.warning) for r in m.curves if r.included],
            )
            for m in batch
        ]
    grouped: dict[int, dict[int, list[WindowRow]]] = defaultdict(lambda: defaultdict(list))
    for row in batch.rows:
        if row.curve is not None:
            grouped[row.source_index][row.curve].append(row)
    maps = []
    for j, path in enumerate(batch.source_paths):
        groups = grouped[j]
        panels = []
        digest = ""
        for index, rows in groups.items():
            digest = rows[0].sha256
            windows = tuple(r.window for r in rows if r.window is not None)
            panels.append(CurvePanel(index, windows, note=rows[0].reason))
        maps.append(FigureMap(path, digest, panels))
    return maps


def render_panel(
    curve: ForceCurve | None, panel: CurvePanel, source: str, branch: str, mode: str
) -> Figure:
    """Render the full branches and independently autoscaled details from native samples."""
    from matplotlib.axes import Axes

    spans = [(w.start, w.end) for w in panel.windows]
    minima = [w.boundary for w in panel.windows]
    branches = (
        {}
        if curve is None
        else {
            key: seg
            for key, seg in (("extend", curve.extend), ("retract", curve.retract))
            if seg is not None and seg.force is not None
        }
    )
    active = branches.get(branch)
    adh = panel.adhesion
    if (
        active is not None
        and adh is not None
        and adh.minimum_index is not None
        and adh.baseline_points
    ):
        spans = [(len(active) - adh.baseline_points, len(active) - 1)]
        minima = [adh.minimum_index]
    # A common x coordinate is required for comparing branches on the overview.
    separate = bool(branches) and all(
        s.separation is not None and np.isfinite(s.separation).all() and np.ptp(s.separation) > 0
        for s in branches.values()
    )
    xlabel = "Separación punta–muestra (nm)" if separate else "Altura del sensor (nm)"
    if separate and any(
        s.metadata.get("separation_status") == "unverified" for s in branches.values()
    ):
        xlabel = "Separación del instrumento sin contraste (nm)"
    traces = {}
    for key, s in branches.items():
        axis = s.separation if separate else s.raw_height
        traces[key] = (np.asarray(axis) * 1e9, np.asarray(s.force) * 1e9)
    # More than four windows share neighbouring detail panels. All windows remain marked.
    groups = (
        [g.tolist() for g in np.array_split(np.arange(len(spans)), min(4, len(spans)))]
        if spans
        else []
    )
    rows = 1 + (len(groups) + 1) // 2
    height = 1.25 + 2.55 * rows
    fig = Figure(figsize=(9.6, height), facecolor="white")
    FigureCanvasAgg(fig)
    layout = fig.add_gridspec(
        rows,
        2,
        left=0.115,
        right=0.975,
        bottom=0.66 / height,
        top=1 - 1.04 / height,
        hspace=0.92,
        wspace=0.37,
    )
    overview = fig.add_subplot(layout[0, :])
    title = {
        "steps": "Escalones de fuerza",
        "contact": "Contacto · Hertz esférico",
        "adhesion": "Adhesión",
    }[mode]
    fig.text(0.055, 1 - 0.20 / height, title, va="top", size=16, weight="bold", color="#162e40")
    short_source = source if len(source) <= 40 else source[:22] + "…" + source[-15:]
    fig.text(
        0.055,
        1 - 0.53 / height,
        f"{short_source}   ·   Curva {panel.index}",
        size=10.5,
        va="top",
        parse_math=False,
    )
    handles: list[Artist] = []
    for key, (x, y) in traces.items():
        label, color, ls = _BRANCHES[key]
        (line,) = overview.plot(x, y, color=color, ls=ls, lw=1.45, label=label)
        handles.append(line)

    def decorate(ax: Axes) -> None:
        ax.set_xlabel(xlabel, fontsize=10.5)
        ax.set_ylabel("Fuerza (nN)", fontsize=10.5)
        ax.tick_params(labelsize=10, colors="#384854")
        ax.ticklabel_format(useOffset=False)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dfe5e8", lw=0.65)
        ax.set_axisbelow(True)
        ax.margins(x=0.04, y=0.12)

    def highlight(ax: Axes, indices: Sequence[int]) -> None:
        x, y = traces[branch]
        for j in indices:
            a, b = spans[j]
            region = x[a : b + 1]
            if (
                len(region)
                and np.isfinite(region).all()
                and (np.all(np.diff(region) >= 0) or np.all(np.diff(region) <= 0))
            ):
                ax.axvspan(
                    float(region.min()), float(region.max()), facecolor=_HIGHLIGHT, alpha=0.12, lw=0
                )
            ax.plot(x[a : b + 1], y[a : b + 1], lw=2.8, color=_HIGHLIGHT, solid_capstyle="round")
            k = minima[j]
            ax.plot(x[k], y[k], "o", color=_MARK, ms=4.5)

    decorate(overview)
    overview.set_title(
        f"Curva completa · análisis en {_BRANCHES[branch][0].lower()}", loc="left", size=11
    )
    if spans and branch in traces:
        handles.extend(
            [
                Patch(facecolor=_HIGHLIGHT, label="Referencia de cola" if adh else "Ventana"),
                Line2D(
                    [], [], marker="o", ls="", color=_MARK, label="Mínimo" if adh else "Frontera"
                ),
            ]
        )
        highlight(overview, range(len(spans)))
        for n, group in enumerate(groups):
            detail = fig.add_subplot(
                layout[1 + n // 2, :]
                if len(groups) % 2 and n == len(groups) - 1
                else layout[1 + n // 2, n % 2]
            )
            x, y = traces[branch]
            start, end = spans[group[0]][0], spans[group[-1]][1]
            pad = max(4, (end - start + 1) // 2)
            if adh:
                start = end = minima[0]
            sl = slice(max(0, start - pad), min(len(x), end + pad + 1))
            detail.plot(x[sl], y[sl], color=_BRANCHES[branch][1], lw=1.55)
            if adh:
                detail.plot(x[start], y[start], "o", color=_MARK, ms=4.5)
                label = (
                    f"Mínimo de retracción · adhesión {adh.adhesion_n*1e9:.4g} nN"
                    if adh.adhesion_n is not None
                    else "Mínimo de retracción"
                )
            else:
                highlight(detail, group)
                label = f"Muestras {start}–{end}"
                if len(group) == 1:
                    w = panel.windows[group[0]]
                    if w.delta_force_n is not None:
                        label += f"   ·   ΔF {w.delta_force_n*1e9:+.4g} nN"
                    elif w.modulus_pa is not None:
                        label += f"   ·   E {w.modulus_pa/1e3:.4g} kPa"
            detail.set_title(label, loc="left", size=10.5)
            decorate(detail)
    if handles:
        fig.legend(
            handles=handles,
            loc="upper right",
            bbox_to_anchor=(0.985, 1 - 0.10 / height),
            ncol=2,
            fontsize=10,
            frameon=False,
            columnspacing=1.2,
        )
    if panel.note:
        overview.set_title(shorten(panel.note, width=90, placeholder="…"), loc="left", size=10)
    return fig


def export_batch_figures(
    batch: WindowBatch | Sequence[AdhesionMap],
    parent: Path,
    progress: Callable[[float, str], None] | None = None,
) -> Path:
    """Publish only complete runs; use a unique directory and validate inputs against the review."""
    maps = _maps(batch)
    total = sum(len(m.panels) for m in maps)
    if total == 0:
        raise ValueError("No hay curvas seleccionadas para exportar")
    automatic = isinstance(batch, WindowBatch)
    mode = batch.options.mode if isinstance(batch, WindowBatch) else "adhesion"
    branch = batch.options.branch if isinstance(batch, WindowBatch) else "retract"
    target = parent / f"figuras_{mode}_{uuid4().hex[:10]}"
    with TemporaryDirectory(dir=parent, prefix=".fathom-") as tmp:
        run = Path(tmp) / "figuras"
        run.mkdir()
        if isinstance(batch, WindowBatch):
            batch.to_csv(run / "ventanas.csv")
        else:
            export_review(batch, run / "seleccion.csv", summary=False)
        done = 0
        with (run / "indice.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                ("imagen", "mapa", "archivo", "sha256", "curva", "modo", "rama", "ventanas", "nota")
            )
            for j, m in enumerate(maps):
                if not m.panels:
                    continue
                if progress:
                    progress(done / total, m.path.name)
                _, volume = read_for_review(m.path, m.digest)
                directory = run / f"mapa_{j+1:03d}"
                directory.mkdir()
                for panel in m.panels:
                    if progress:
                        progress(done / total, f"{m.path.name} · figura {done+1}/{total}")
                    try:
                        curve = volume.curve(panel.index)
                    except (ValueError, ArithmeticError) as exc:
                        if panel.windows or (
                            panel.adhesion and panel.adhesion.adhesion_n is not None
                        ):
                            raise
                        curve = None
                        panel = replace(panel, note=f"Curva no disponible · {exc}")
                    fig = render_panel(curve, panel, m.path.name, branch, mode)
                    png = directory / f"curva_{panel.index:05d}.png"
                    try:
                        fig.savefig(png, dpi=300, format="png")
                    finally:
                        fig.clear()
                    writer.writerow(
                        (
                            png.relative_to(run).as_posix(),
                            j,
                            m.path.name,
                            m.digest,
                            panel.index,
                            mode,
                            branch,
                            (
                                len(panel.windows)
                                if automatic
                                else int(
                                    panel.adhesion is not None
                                    and panel.adhesion.minimum_index is not None
                                )
                            ),
                            panel.note,
                        )
                    )
                    done += 1
                del volume
        if progress:
            progress(1.0, f"{done} figuras")
        run.rename(target)
    return target
