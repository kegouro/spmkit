"""Exportación integral de un force-volume — «exportar todo» en una carpeta.

Produce, para un ``ForceVolume``:

* un CSV por mapa de propiedad (``mapa_young_modulus.csv``, …),
* una tabla por curva (índice, fila, columna y todas las propiedades),
* un resumen estadístico (mediana, σ, rango, N por propiedad),
* el **informe** (HTML + PDF) de :mod:`spmkit.core.forcereport`.

Todo con la ruta vectorizada (CPU/GPU). Requiere el extra ``report`` para el informe.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.analysis.forcevolume import PROPERTY_UNITS, analyze_volume
from spmkit.core.analysis.forcevolume_fast import elasticity_map
from spmkit.core.models import ForceVolume
from spmkit.core.pipeline import Recipe


def _write_curve_table(result: Any, volume: ForceVolume, path: Path) -> None:
    """CSV con una fila por curva: índice, (fila, col), (x, y) y cada propiedad."""
    rows, cols = volume.grid_shape
    keys = list(result.maps)
    dx = volume.x_range / cols if cols else 0.0
    dy = volume.y_range / rows if rows else 0.0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["index", "row", "col", "x_m", "y_m", *keys])
        flats = {k: result.maps[k].ravel() for k in keys}
        for i in range(volume.n_curves):
            r, c = divmod(i, cols)
            writer.writerow(
                [i, r, c, f"{c * dx:.6e}", f"{r * dy:.6e}", *(f"{flats[k][i]:.6e}" for k in keys)]
            )


def _write_summary(result: Any, path: Path) -> None:
    """CSV con la estadística robusta por propiedad."""
    keys = list(result.maps)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["property", "median", "std", "min", "max", "n"])
        for k in keys:
            s = result.stats(k)
            writer.writerow([k, s["median"], s["std"], s["min"], s["max"], s["n"]])


def export_bundle(
    volume: ForceVolume,
    out_dir: str | Path,
    *,
    source_name: str = "",
    model: str = "sphere",
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    backend: str = "cpu",
    report_formats: tuple[str, ...] = ("html", "pdf"),
    recipe: Recipe | None = None,
) -> dict[str, Path]:
    """Exporta **todo** de ``volume`` a ``out_dir``; devuelve el manifiesto de archivos."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = (
        analyze_volume(volume, recipe, keys=tuple(PROPERTY_UNITS))
        if recipe is not None
        else elasticity_map(
            volume, tip_radius=tip_radius, poisson=poisson, model=model, backend=backend
        )
    )

    manifest: dict[str, Path] = {}
    if recipe is not None:
        metadata = out / "analisis.json"
        metadata.write_text(
            json.dumps(
                {"source": source_name, "recipe": recipe.to_dict(), "units": PROPERTY_UNITS},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest["analysis"] = metadata
    for key, arr in result.maps.items():
        p = out / f"mapa_{key}.csv"
        np.savetxt(p, arr, delimiter=",")
        manifest[f"map_{key}"] = p

    table = out / "curvas_resultados.csv"
    _write_curve_table(result, volume, table)
    manifest["table"] = table

    summary = out / "resumen_estadistica.csv"
    _write_summary(result, summary)
    manifest["summary"] = summary

    if report_formats:
        try:
            from spmkit.core.forcereport import build_force_report

            produced = build_force_report(
                volume,
                out / "informe",
                source_name=source_name or out.name,
                model=model,
                tip_radius=tip_radius,
                poisson=poisson,
                backend=backend,
                formats=report_formats,
                recipe=recipe,
            )
            manifest.update({f"report_{k}": v for k, v in produced.items()})
        except ImportError:  # pragma: no cover - sin extra report: se omite el informe
            pass

    return manifest
