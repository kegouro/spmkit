"""Procesamiento por lotes de múltiples archivos SPM.

Recorre una carpeta (o lista de archivos), aplica el pipeline de análisis a
cada uno y devuelve una tabla resumen, ideal para procesar campañas completas
de medidas del lab.
"""

from __future__ import annotations

import csv as _csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from spmkit.core.analysis import kpfm, leveling, roughness
from spmkit.core.io import load, supported_extensions


@dataclass
class BatchRow:
    """Resumen de un archivo procesado."""

    file: str
    channel: str
    ok: bool
    Sa: float | None = None
    Sq: float | None = None
    Sz: float | None = None
    cpd_mean: float | None = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "channel": self.channel,
            "ok": self.ok,
            "Sa": self.Sa,
            "Sq": self.Sq,
            "Sz": self.Sz,
            "cpd_mean": self.cpd_mean,
            "error": self.error,
        }


@dataclass
class BatchResult:
    """Resultado de un lote: filas + conteo de éxitos/errores."""

    rows: list[BatchRow] = field(default_factory=list)

    @property
    def n_ok(self) -> int:
        return sum(r.ok for r in self.rows)

    @property
    def n_failed(self) -> int:
        return sum(not r.ok for r in self.rows)

    def to_csv(self, path: str | Path) -> Path:
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = _csv.DictWriter(fh, fieldnames=list(BatchRow("", "", True).to_dict()))
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row.to_dict())
        return path


def find_files(folder: str | Path) -> list[Path]:
    """Lista archivos SPM soportados en una carpeta (no recursivo)."""
    folder = Path(folder)
    exts = set(supported_extensions())
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in exts)


def process(
    files: Iterable[str | Path],
    channel: str = "Z-Axis",
    cpd_channel: str = "CPD",
    level: str = "plane",
) -> BatchResult:
    """Analiza una colección de archivos y devuelve la tabla resumen."""
    result = BatchResult()
    for f in files:
        f = Path(f)
        try:
            data = load(f)
            ch = data[channel]
            if level == "plane":
                ch = leveling.plane_fit(ch)
            elif level == "poly":
                ch = leveling.polynomial(ch, order=2)
            stats = roughness.statistics(ch)
            cpd_mean = None
            if cpd_channel in data.names:
                cpd_mean = kpfm.statistics(data[cpd_channel]).mean
            result.rows.append(
                BatchRow(
                    file=f.name,
                    channel=channel,
                    ok=True,
                    Sa=stats.Sa,
                    Sq=stats.Sq,
                    Sz=stats.Sz,
                    cpd_mean=cpd_mean,
                )
            )
        except Exception as exc:  # noqa: BLE001 - registrar fallo y continuar
            result.rows.append(BatchRow(file=f.name, channel=channel, ok=False, error=str(exc)))
    return result
