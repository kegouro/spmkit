"""Procesamiento por lotes de curvas de fuerza (reemplaza el batch de ANA/JPK).

Corre un :class:`Recipe` reproducible sobre todos los archivos de curvas de fuerza de
una carpeta (``.jpk-force`` y ``.nid``), tolerando errores por archivo, y arma una
tabla resumen con la estadística de cada propiedad (módulo, adhesión, disipación).
Exporta a CSV y —si hay pandas— a ``DataFrame``.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from spmkit.core.analysis.forcevolume import DEFAULT_KEYS, analyze_volume
from spmkit.core.io.jpk import load_jpk_force
from spmkit.core.io.nid import load_nid_force
from spmkit.core.models import ForceVolume
from spmkit.core.pipeline import Recipe

#: Extensiones de curvas de fuerza soportadas por el batch.
FORCE_EXTENSIONS = (".jpk-force", ".nid")


def load_force(path: str | Path) -> ForceVolume:
    """Carga un archivo de curvas de fuerza como :class:`ForceVolume` (por extensión).

    ``.nid`` → force-volume completo; ``.jpk-force`` → una curva envuelta en un volumen
    1×1 (para un flujo de batch uniforme).
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".nid":
        return load_nid_force(path)
    if ext == ".jpk-force":
        curve = load_jpk_force(path)
        return ForceVolume.from_curves([curve], grid_shape=(1, 1), x_range=0.0, y_range=0.0)
    raise ValueError(f"Extensión de curva de fuerza no soportada: {ext!r}")


@dataclass
class ForceBatchRow:
    """Resumen de un archivo procesado en el batch."""

    source: str
    n_curves: int = 0
    n_ok: int = 0
    young_modulus_median: float = float("nan")
    young_modulus_std: float = float("nan")
    adhesion_median: float = float("nan")
    dissipation_median: float = float("nan")
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ForceBatchResult:
    """Resultado del batch: una fila por archivo."""

    rows: list[ForceBatchRow] = field(default_factory=list)

    @property
    def n_ok(self) -> int:
        return sum(1 for r in self.rows if not r.error)

    @property
    def n_failed(self) -> int:
        return sum(1 for r in self.rows if r.error)

    def to_csv(self, path: str | Path) -> None:
        """Escribe la tabla resumen a CSV (una fila por archivo)."""
        path = Path(path)
        fields = list(ForceBatchRow(source="").to_dict().keys())
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row.to_dict())

    def to_dataframe(self) -> Any:
        """Devuelve un ``pandas.DataFrame`` (requiere el extra ``pandas``)."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - camino opcional
            raise ImportError("to_dataframe requiere pandas: pip install 'spmkit[pandas]'") from exc
        return pd.DataFrame([r.to_dict() for r in self.rows])


def process_force_folder(
    folder: str | Path,
    recipe: Recipe,
    keys: tuple[str, ...] = DEFAULT_KEYS,
    parallel: bool = False,
    pattern: str = "*",
) -> ForceBatchResult:
    """Procesa todas las curvas de fuerza de ``folder`` con ``recipe``.

    Recorre los archivos ``.jpk-force``/``.nid`` (según ``pattern``), corre el pipeline
    en cada uno y resume la estadística por archivo. Un archivo que falla queda con su
    error en la fila, sin abortar el lote.
    """
    folder = Path(folder)
    files = sorted(
        f for f in folder.glob(pattern) if f.suffix.lower() in FORCE_EXTENSIONS and f.is_file()
    )
    rows: list[ForceBatchRow] = []
    for f in files:
        try:
            volume = load_force(f)
            result = analyze_volume(volume, recipe, keys=keys, parallel=parallel)
            e_stats = result.stats("young_modulus") if "young_modulus" in result.maps else {}
            adh_stats = result.stats("adhesion") if "adhesion" in result.maps else {}
            dis_stats = result.stats("dissipation") if "dissipation" in result.maps else {}
            rows.append(
                ForceBatchRow(
                    source=f.name,
                    n_curves=volume.n_curves,
                    n_ok=result.n_ok,
                    young_modulus_median=e_stats.get("median", float("nan")),
                    young_modulus_std=e_stats.get("std", float("nan")),
                    adhesion_median=adh_stats.get("median", float("nan")),
                    dissipation_median=dis_stats.get("median", float("nan")),
                )
            )
        except Exception as exc:  # noqa: BLE001 - un archivo malo no aborta el lote
            rows.append(ForceBatchRow(source=f.name, error=str(exc)))
    return ForceBatchResult(rows=rows)
