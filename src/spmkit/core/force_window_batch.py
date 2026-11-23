"""Process explicitly selected NID maps, retaining an outcome for every curve."""

from __future__ import annotations

import csv
import os
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from spmkit import __version__
from spmkit.core.analysis.force_windows import AutoWindow, WindowOptions, select_windows
from spmkit.core.export.manifest import file_sha256, get_git_commit
from spmkit.core.io.nid import load_nid_force
from spmkit.core.models import ForceSegment


@dataclass(frozen=True)
class WindowRow:
    source: str
    sha256: str
    curve: int | None
    status: str
    reason: str = ""
    window: AutoWindow | None = None
    preview: tuple[np.ndarray, np.ndarray] | None = None


@dataclass
class WindowBatch:
    options: WindowOptions
    rows: list[WindowRow]
    revision: str | None

    def to_csv(self, path: Path) -> None:
        if path.suffix.lower() != ".csv":
            raise ValueError("Selecciona un destino .csv")
        provenance = {
            "method": f"nid-{self.options.mode}-v1",
            "version": __version__,
            "revision": self.revision,
            "mode": self.options.mode,
            "branch": self.options.branch,
            "cycle": 0,
            "sigma": self.options.sigma,
        }
        if self.options.mode == "contact":
            provenance.update(
                tip_radius_nm=self.options.tip_radius_nm,
                poisson=self.options.poisson,
                max_depth_nm=self.options.max_depth_nm,
            )
        else:
            provenance["flank"] = self.options.flank
        keys = [f.name for f in fields(AutoWindow)]
        with NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=path.parent, delete=False
        ) as out:
            tmp = Path(out.name)
        try:
            with tmp.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "source",
                        "sha256",
                        "curve",
                        "status",
                        "reason",
                        *keys,
                        *provenance,
                    ],
                )
                writer.writeheader()
                for row in self.rows:
                    info = {
                        "source": row.source,
                        "sha256": row.sha256,
                        "curve": row.curve,
                        "status": row.status,
                        "reason": row.reason,
                    }
                    window = asdict(row.window) if row.window is not None else {}
                    writer.writerow({**info, **window, **provenance})
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def _preview(
    seg: ForceSegment | None, w: AutoWindow | None
) -> tuple[np.ndarray, np.ndarray] | None:
    if seg is None or seg.force is None or not len(seg.force):
        return None
    lo, hi = 0, len(seg.force)
    anchors = []
    if w is not None:
        pad = max(8, (w.end - w.start + 1) // 2)
        lo, hi = max(0, w.start - pad), min(hi, w.end + pad + 1)
        anchors = [w.start, max(0, w.boundary - 1), w.boundary, w.end]
    if hi - lo <= 200:
        indices = np.arange(lo, hi)
    else:
        # Include both extrema of every bin so narrow peaks survive the overview.
        edges = np.linspace(lo, hi, 101, dtype=int)
        selected = [lo, *anchors, hi - 1]
        for a, b in zip(edges[:-1], edges[1:], strict=True):
            section = seg.force[a:b]
            selected.extend((a + int(np.argmin(section)), a + int(np.argmax(section))))
        indices = np.unique(selected)
    return indices, seg.force[indices] * 1e9


def analyze_window_files(
    paths: Sequence[Path],
    options: WindowOptions,
    progress: Callable[[float, str], None] | None = None,
) -> WindowBatch:
    rows: list[WindowRow] = []
    for j, path in enumerate(paths):
        if progress:
            progress(j / len(paths), path.name)
        digest = ""
        try:
            digest = file_sha256(path)
            volume = load_nid_force(path)
        except (OSError, ValueError) as exc:
            rows.append(WindowRow(path.name, digest, None, "error", str(exc)))
            continue
        for i in range(volume.n_curves):
            if progress and i % 8 == 0:
                progress(
                    (j + i / volume.n_curves) / len(paths), f"{path.name} · {i+1}/{volume.n_curves}"
                )
            segment = None
            try:
                curve = volume.curve(i)
                segment = curve.segment(options.branch, 0)
                windows = select_windows(curve, options)
            except (ValueError, ArithmeticError, RuntimeError) as exc:
                rows.append(
                    WindowRow(
                        path.name, digest, i, "revisar", str(exc), preview=_preview(segment, None)
                    )
                )
                continue
            if not windows:
                rows.append(
                    WindowRow(
                        path.name,
                        digest,
                        i,
                        "sin candidato",
                        "Sin salto aislado que supere los criterios",
                        preview=_preview(segment, None),
                    )
                )
            for w in windows:
                rows.append(
                    WindowRow(
                        path.name, digest, i, "candidato", window=w, preview=_preview(segment, w)
                    )
                )
        del volume
    if progress:
        progress(1.0, "Completado")
    return WindowBatch(options, rows, get_git_commit())
