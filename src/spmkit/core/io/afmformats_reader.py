"""Lector opcional respaldado por **afmformats** — amplía la cola de formatos.

`afmformats` (MIT, Paul Müller) lee JPK QI/force-map, Asylum ``.ibw``, HDF5, NT-MDT,
``.tab``/``.csv`` de curvas de fuerza. Este adaptador los mapea a nuestro
:class:`ForceVolume`, reutilizando nuestra nanomecánica validada. Se registra solo si el
extra ``afm`` está instalado (``pip install 'spmkit[afm]'``); ``.jpk-force`` lo maneja el
lector nativo, ya validado.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spmkit.core.plugins.contracts import DatasetInfo, Kind

#: Extensiones que delegamos a afmformats (``.jpk-force`` queda al lector nativo).
AFMFORMATS_EXTENSIONS: tuple[str, ...] = (
    ".jpk-qi-data",
    ".jpk-force-map",
    ".jpk-qi-series",
    ".ibw",
    ".h5",
    ".tab",
)


def _segment(seg: Any, kind: str, direction: str) -> Any:
    import numpy as np

    from spmkit.core.models import ForceSegment

    force = np.asarray(seg["force"], dtype=np.float64)
    height = np.asarray(seg["height (measured)"], dtype=np.float64)
    return ForceSegment(
        segment_type=kind,  # type: ignore[arg-type]
        direction=direction,
        raw_height=height,
        raw_deflection=force,  # ya calibrada (state force_n); no se usa el crudo
        force=force,
        separation=height,
        state="force_n",
    )


class AfmformatsReader:
    """Adaptador de ``afmformats`` a :class:`ForceVolume` (curvas de fuerza)."""

    extensions: tuple[str, ...] = AFMFORMATS_EXTENSIONS

    def inspect(self, path: str | Path) -> DatasetInfo:
        # Barato: afmformats no ofrece peek de solo-metadatos; declaramos 'force' por
        # extensión (todos estos formatos son curvas de fuerza).
        return DatasetInfo(path=Path(path), format="afmformats", kinds=("force",))

    def load(self, path: str | Path, kind: Kind | None = None) -> Any:
        import afmformats

        from spmkit.core.models import ForceCurve, ForceVolume

        groups = afmformats.load_data(str(path))
        curves = []
        for i, c in enumerate(groups):
            segments = []
            if len(c.appr["force"]):
                segments.append(_segment(c.appr, "extend", "approach"))
            if len(c.retr["force"]):
                segments.append(_segment(c.retr, "retract", "retract"))
            px, py = c.metadata.get("position x"), c.metadata.get("position y")
            position = (float(px), float(py)) if px is not None and py is not None else None
            curves.append(
                ForceCurve(
                    segments=tuple(segments),
                    position=position,
                    index=i,
                    metadata={"format": "afmformats"},
                )
            )

        n = len(curves)
        meta = groups[0].metadata if groups else {}
        gx = int(meta.get("grid shape x", 0) or 0)
        gy = int(meta.get("grid shape y", 0) or 0)
        grid = (gy, gx) if n and gx * gy == n else (1, n)
        return ForceVolume.from_curves(
            curves,
            grid_shape=grid,
            x_range=float(meta.get("grid size x", 0) or 0),
            y_range=float(meta.get("grid size y", 0) or 0),
        )
