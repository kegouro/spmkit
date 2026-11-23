"""Procesamiento por lotes de curvas de fuerza (reemplaza el batch de ANA/JPK).

Corre un :class:`Recipe` reproducible sobre todos los archivos de curvas de fuerza de
una carpeta (``.jpk-force`` y ``.nid``), tolerando errores por archivo, y arma una
tabla resumen con la estadística de cada propiedad (módulo, adhesión, disipación).
Exporta a CSV y —si hay pandas— a ``DataFrame``.
"""

from __future__ import annotations

import csv
import json
import math
import stat
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO, Any

from spmkit import __version__
from spmkit.core.analysis.forcevolume import DEFAULT_KEYS, analyze_volume
from spmkit.core.export.manifest import file_sha256, get_git_commit
from spmkit.core.io.jpk import load_jpk_force
from spmkit.core.io.nid import load_nid_force
from spmkit.core.models import ForceVolume
from spmkit.core.pipeline import Recipe

#: Extensiones de curvas de fuerza soportadas por el batch.
FORCE_EXTENSIONS = (".jpk-force", ".nid")

#: Unidad física de cada columna numérica del resumen (para encabezados trazables).
_ROW_UNITS: dict[str, str] = {
    "young_modulus_median": "Pa",
    "young_modulus_std": "Pa",
    "adhesion_median": "N",
    "dissipation_median": "J",
}


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
    n_young_modulus: int = 0
    n_adhesion: int = 0
    n_dissipation: int = 0
    source_sha256: str = ""

    @property
    def n_curves_failed(self) -> int:
        return self.n_curves - self.n_ok

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "n_curves_failed": self.n_curves_failed}


@dataclass
class ForceBatchResult:
    """Resultado del batch: una fila por archivo."""

    rows: list[ForceBatchRow] = field(default_factory=list)

    recipe: dict[str, Any] | None = None
    keys: tuple[str, ...] = ()
    git_commit: str | None = None

    @property
    def n_ok(self) -> int:
        return sum(1 for r in self.rows if not r.error)

    @property
    def n_failed(self) -> int:
        return sum(1 for r in self.rows if r.error)

    @property
    def n_curves(self) -> int:
        return sum(row.n_curves for row in self.rows)

    @property
    def n_curves_ok(self) -> int:
        return sum(row.n_ok for row in self.rows)

    @property
    def n_curves_failed(self) -> int:
        return self.n_curves - self.n_curves_ok

    def to_csv(self, path: str | Path) -> None:
        """Escribe la tabla resumen a CSV científico (una fila por archivo).

        Lleva una cabecera de metadatos (``#``: archivos, OK/fallidos), **unidades** en los
        encabezados numéricos y **celdas vacías** en vez de ``NaN`` (una propiedad sin datos
        —p. ej. disipación sin retracción— no ensucia el archivo).
        """
        path = Path(path)
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w", newline="", encoding="utf-8", dir=path.parent, delete=False
            ) as fh:
                temporary = Path(fh.name)
                self._write_csv(fh)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _write_csv(self, fh: IO[str]) -> None:
        fields = list(ForceBatchRow(source="").to_dict())
        fh.write("# spmkit — resumen de lote de curvas/mapas de fuerza\n")
        fh.write(
            f"# archivos: {len(self.rows)}  ·  OK: {self.n_ok}  ·  fallidos: {self.n_failed}\n"
        )
        fh.write(
            f"# curvas cargadas: {self.n_curves}  ·  procesadas: {self.n_curves_ok}"
            f"  ·  fallidas: {self.n_curves_failed}\n#\n"
        )
        if self.recipe is not None:
            provenance = {
                "spmkit_version": __version__,
                "git_commit": self.git_commit,
                "recipe": self.recipe,
                "keys": self.keys,
            }
            fh.write("# " + json.dumps(provenance, ensure_ascii=False, sort_keys=True) + "\n")
        writer = csv.writer(fh)
        writer.writerow([f"{f} [{_ROW_UNITS[f]}]" if f in _ROW_UNITS else f for f in fields])
        for row in self.rows:
            d = row.to_dict()
            writer.writerow(
                [
                    "" if isinstance(d[f], float) and not math.isfinite(d[f]) else d[f]
                    for f in fields
                ]
            )

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
    progress: Callable[[float, str], None] | None = None,
) -> ForceBatchResult:
    """Procesa todas las curvas de fuerza de ``folder`` con ``recipe``.

    Recorre los archivos ``.jpk-force``/``.nid`` (según ``pattern``), corre el pipeline
    en cada uno y resume la estadística por archivo. Un archivo que falla queda con su
    error en la fila, sin abortar el lote. ``progress(fracción, nombre)`` se invoca
    durante cada mapa y al finalizar cada archivo. Puede interrumpir el lote lanzando
    una excepción.
    """
    folder = Path(folder)
    if not stat.S_ISDIR(folder.stat().st_mode):
        raise NotADirectoryError(f"No es una carpeta: {folder}")
    files = sorted(
        f for f in folder.glob(pattern) if f.suffix.lower() in FORCE_EXTENSIONS and f.is_file()
    )
    total = len(files)

    def summarize(index: int, path: Path) -> ForceBatchRow:
        row = ForceBatchRow(source=str(path.relative_to(folder)))
        callback_error: Exception | None = None
        last_percent = 0

        def progress_in_map(fraction: float, _: int) -> None:
            nonlocal callback_error, last_percent
            percent = int(fraction * 100)
            if progress is not None and last_percent < percent < 100:
                last_percent = percent
                try:
                    progress((index + fraction) / total, path.name)
                except Exception as exc:
                    callback_error = exc
                    raise

        try:
            row.source_sha256 = file_sha256(path)
            volume = load_force(path)
            row.n_curves = volume.n_curves
            result = analyze_volume(
                volume,
                recipe,
                keys=keys,
                parallel=parallel,
                progress=progress_in_map if progress is not None else None,
            )
            row.n_ok = result.n_ok
            if result.n_ok == 0:
                row.error = "Ninguna curva procesada"
                if result.first_error:
                    row.error += f": {result.first_error}"
            e_stats = result.stats("young_modulus") if "young_modulus" in result.maps else {}
            adh_stats = result.stats("adhesion") if "adhesion" in result.maps else {}
            dis_stats = result.stats("dissipation") if "dissipation" in result.maps else {}
            row.n_young_modulus = int(e_stats.get("n", 0))
            row.n_adhesion = int(adh_stats.get("n", 0))
            row.n_dissipation = int(dis_stats.get("n", 0))
            row.young_modulus_median = e_stats.get("median", float("nan"))
            row.young_modulus_std = e_stats.get("std", float("nan"))
            row.adhesion_median = adh_stats.get("median", float("nan"))
            row.dissipation_median = dis_stats.get("median", float("nan"))
        except Exception as exc:  # noqa: BLE001 - un archivo malo no aborta el lote
            if exc is callback_error:
                raise
            row.error = str(exc) or type(exc).__name__
        return row

    rows: list[ForceBatchRow] = []
    if progress is not None and not files:
        progress(1.0, "Sin archivos de curvas compatibles")
    for i, path in enumerate(files):
        if progress is not None:
            progress(i / total, path.name)
        rows.append(summarize(i, path))
        if progress is not None:
            progress((i + 1) / total, path.name)
    return ForceBatchResult(
        rows=rows, recipe=recipe.to_dict(), keys=keys, git_commit=get_git_commit()
    )
