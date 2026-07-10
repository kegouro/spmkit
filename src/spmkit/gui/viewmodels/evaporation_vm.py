"""ViewModel de la serie de evaporación — sensado de masa por desplazamiento de frecuencia.

Carga una carpeta de espectros de *thermal tuning* (``.nid``), sigue la resonancia en el
tiempo y deriva masa, masa añadida, tasa de evaporación y el ajuste de la ley d² (misma
física que el comando ``spmkit evaporation``). Autocontenido: no depende del hub de imagen;
el panel elige la carpeta. El cómputo es barato (espectros chicos), así que corre síncrono.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import resonance


@dataclass(frozen=True)
class EvaporationResult:
    """Serie de evaporación + radios de gota + ajuste de la ley d², listos para dibujar."""

    series: resonance.EvaporationSeries
    radius: np.ndarray  # m, radio de gota por instante (gota esférica)
    d2: resonance.D2LawResult


class EvaporationViewModel(QObject):
    """Estado observable del sensado de masa por evaporación de una serie de ``.nid``."""

    resultChanged = pyqtSignal(object)  # EvaporationResult (o None al invalidar)
    statusChanged = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None
        self._x_over_l: float = 1.0
        self._spring_constant: float | None = None  # None = usar la del archivo
        self._result: EvaporationResult | None = None

    @property
    def result(self) -> EvaporationResult | None:
        return self._result

    @property
    def position(self) -> float:
        return self._x_over_l

    @property
    def spring_constant(self) -> float | None:
        return self._spring_constant

    def load_folder(self, folder: str | Path) -> None:
        """Carga los ``.nid`` de ``folder`` como serie de evaporación y recalcula."""
        self._folder = Path(folder)
        self._compute()

    def set_position(self, x_over_l: float) -> None:
        """Posición de carga ``x/L`` (micrografía); ``k(x)=k(L)/(x/L)³``. Recalcula."""
        self._x_over_l = float(x_over_l)
        self._compute()

    def set_spring_constant(self, k: float | None) -> None:
        """Constante de resorte k(L) (N/m); ``None``/``0`` = la del archivo. Recalcula."""
        self._spring_constant = float(k) if k else None
        self._compute()

    def _compute(self) -> None:
        if self._folder is None:
            self._emit(None)
            return
        files = sorted(self._folder.glob("*.nid"))
        if len(files) < 2:
            self.statusChanged.emit("evaporación: se necesitan ≥2 espectros de sintonía térmica")
            self._emit(None)
            return
        try:
            series = resonance.load_evaporation_series(
                files, spring_constant=self._spring_constant, x_over_l=self._x_over_l
            )
            radius = np.asarray(resonance.droplet_radius(series.added_mass), dtype=np.float64)
            d2 = resonance.fit_d2_law(series.time, radius)
        except Exception as exc:  # noqa: BLE001 - carpeta sin serie válida de thermal tuning
            self.statusChanged.emit(f"evaporación: {exc}")
            self._emit(None)
            return
        self.statusChanged.emit(
            f"{len(series.time)} espectros · Δm₀ = {series.added_mass[0] * 1e12:.3g} ng · "
            f"τ = {d2.tau / 3600:.3g} h"
            if np.isfinite(d2.tau)
            else f"{len(series.time)} espectros"
        )
        self._emit(EvaporationResult(series=series, radius=radius, d2=d2))

    def export_csv(self, path: str | Path) -> bool:
        """Exporta la serie a CSV (tiempo, frecuencia, masa, masa añadida, tasa). En SI."""
        if self._result is None:
            return False
        import csv

        s = self._result.series
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time_s", "frequency_Hz", "mass_kg", "added_mass_kg", "evap_rate_kg_s"])
            for i in range(len(s.time)):
                w.writerow(
                    [s.time[i], s.frequency[i], s.mass[i], s.added_mass[i], s.evaporation_rate[i]]
                )
        return True

    def _emit(self, result: EvaporationResult | None) -> None:
        self._result = result
        self.resultChanged.emit(result)
