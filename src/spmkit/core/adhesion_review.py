"""Review complete NID force volumes. Pull-off magnitude is relative to the retract tail."""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

import numpy as np

from spmkit import __version__
from spmkit.core.export.manifest import file_sha256
from spmkit.core.io.nid import load_nid_force
from spmkit.core.models import ForceCurve, ForceVolume

METHOD = "nid-retract-tail-median-v1"


@dataclass
class PullOff:
    index: int
    included: bool = True
    adhesion_n: float | None = None
    minimum_index: int | None = None
    baseline_n: float | None = None
    baseline_points: int | None = None
    tail_noise_n: float | None = None
    warning: str = ""


def measure_retract(curve: ForceCurve, index: int) -> PullOff:
    seg = curve.retract
    if seg is None or seg.state != "force_n" or seg.force is None:
        return PullOff(index, warning="Falta retracción calibrada")
    f = np.asarray(seg.force, dtype=float)
    if f.ndim != 1 or len(f) < 10 or not np.isfinite(f).all():
        return PullOff(index, warning="Retracción corta o con valores no finitos")
    count = max(5, int(np.ceil(len(f) * 0.1)))
    tail = f[-count:]
    baseline = float(np.median(tail))
    noise = float(1.4826 * np.median(np.abs(tail - baseline)))
    i = int(np.argmin(f))
    amplitude = max(0.0, baseline - float(f[i]))
    warnings = []
    if i == 0 or i >= len(f) - count:
        warnings.append("Mínimo al inicio o en la zona de referencia")
    if amplitude <= 3 * noise:
        warnings.append("Amplitud dentro de 3 escalas de ruido de la cola")
    if 0 < i < len(f) - 1 and min(f[i - 1], f[i + 1]) - f[i] > max(3 * noise, 0.8 * amplitude):
        warnings.append("Mínimo concentrado en una sola muestra")
    return PullOff(index, True, amplitude, i, baseline, count, noise, " · ".join(warnings))


@dataclass
class AdhesionMap:
    path: Path
    digest: str
    shape: tuple[int, int] = (0, 0)
    curves: list[PullOff] = field(default_factory=list)
    error: str = ""

    def selected_values(self) -> list[float]:
        return [r.adhesion_n for r in self.curves if r.included and r.adhesion_n is not None]


def read_for_review(path: Path, expected: str = "") -> tuple[str, ForceVolume]:
    before = path.stat()
    digest = file_sha256(path)
    if expected and digest != expected:
        raise ValueError("El archivo cambió desde el análisis")
    volume = load_nid_force(path)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("El archivo cambió durante la lectura")
    return digest, volume


def review_maps(
    paths: Sequence[Path], progress: Callable[[float, str], None] | None = None
) -> tuple[list[AdhesionMap], ForceVolume | None]:
    maps = []
    first = None
    for j, path in enumerate(paths):
        if progress:
            progress(j / len(paths), path.name)
        try:
            digest, volume = read_for_review(path)
        except (OSError, ValueError) as exc:
            maps.append(AdhesionMap(path, "", error=str(exc)))
            continue
        m = AdhesionMap(path, digest, volume.grid_shape)
        for i in range(volume.n_curves):
            if progress and i % 32 == 0:
                progress(
                    (j + i / volume.n_curves) / len(paths), f"{path.name} · {i+1}/{volume.n_curves}"
                )
            try:
                row = measure_retract(volume.curve(i), i)
            except (ValueError, ArithmeticError) as exc:
                row = PullOff(i, warning=str(exc))
            m.curves.append(row)
        maps.append(m)
        if first is None:
            first = volume
        del volume
    if progress:
        progress(1.0, "Listo")
    return maps, first


class _TextSink(Protocol):
    def write(self, value: str, /) -> int: ...


@contextmanager
def _csv_destination(path: Path) -> Iterator[_TextSink]:
    if path.suffix.lower() != ".csv":
        raise ValueError("Elige un archivo CSV")
    tmp = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            tmp = Path(stream.name)
            yield stream
        tmp.replace(path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def export_review(maps: Sequence[AdhesionMap], path: Path, *, summary: bool) -> None:
    base = ["source", "sha256", "method", "spmkit_version", "error"]
    keys = (
        ["n_curves", "n_selected", "n_measured_selected", "n_review", "median_adhesion_n"]
        if summary
        else [
            "index",
            "included",
            "adhesion_n",
            "minimum_index",
            "baseline_n",
            "baseline_points",
            "tail_noise_n",
            "warning",
        ]
    )
    with _csv_destination(path) as stream:
        writer = csv.DictWriter(stream, fieldnames=base + keys)
        writer.writeheader()
        for m in maps:
            source = {
                "source": m.path.name,
                "sha256": m.digest,
                "method": METHOD,
                "spmkit_version": __version__,
                "error": m.error,
            }
            if summary:
                vals = m.selected_values()
                writer.writerow(
                    {
                        **source,
                        "n_curves": len(m.curves),
                        "n_selected": sum(r.included for r in m.curves),
                        "n_measured_selected": len(vals),
                        "n_review": sum(bool(r.warning) for r in m.curves),
                        "median_adhesion_n": float(np.median(vals)) if vals else None,
                    }
                )
            elif not m.curves:
                writer.writerow(source)
            else:
                for r in m.curves:
                    writer.writerow({**source, **asdict(r)})


def export_traces(
    maps: Sequence[AdhesionMap], path: Path, progress: Callable[[float, str], None] | None = None
) -> None:
    """Stream full acquired samples, preserving the reviewed source and curve indices."""
    with _csv_destination(path) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "source",
                "sha256",
                "curve",
                "branch",
                "sample",
                "height_m",
                "separation_m",
                "force_n",
                "separation_status",
            )
        )
        for j, m in enumerate(maps):
            selected = [r for r in m.curves if r.included]
            if not selected:
                continue
            if progress:
                progress(j / len(maps), m.path.name)
            _, volume = read_for_review(m.path, m.digest)
            for k, r in enumerate(selected):
                if progress:
                    progress(
                        (j + k / len(selected)) / len(maps),
                        f"{m.path.name} · {k+1}/{len(selected)}",
                    )
                for seg in volume.curve(r.index).segments:
                    for i in range(len(seg)):
                        writer.writerow(
                            (
                                m.path.name,
                                m.digest,
                                r.index,
                                seg.segment_type,
                                i,
                                seg.raw_height[i],
                                seg.separation[i] if seg.separation is not None else None,
                                seg.force[i] if seg.force is not None else None,
                                seg.metadata.get("separation_status", ""),
                            )
                        )
            del volume
        if progress:
            progress(1.0, "Listo")
