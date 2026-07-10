"""ViewModel de sintonía térmica — resonancia del cantiléver desde el hub de imagen.

Corre ``core.analysis.resonance`` sobre el :class:`SPMData` cargado (un ``.nid`` de *thermal
tuning*): extrae el espectro térmico y detecta la resonancia (f0 y Q por ancho a media altura).
Un rango de frecuencia opcional acota la búsqueda del pico. Barato → recalcula al cargar datos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import resonance
from spmkit.gui.viewmodels.image_vm import ImageViewModel


@dataclass(frozen=True)
class ResonanceResult:
    """Espectro térmico + resonancia detectada, listo para dibujar."""

    frequency: np.ndarray  # Hz
    psd: np.ndarray  # densidad espectral (m/√Hz)
    peak: resonance.ResonancePeak  # f0, Q, amplitud, FWHM (detectados)
    reported_f0: float  # f0 reportada por el instrumento (Hz), si la trae
    reported_k: float  # constante de resorte reportada (N/m), si la trae


class ResonanceViewModel(QObject):
    """Estado observable de la sintonía térmica del cantiléver."""

    resultChanged = pyqtSignal(object)  # ResonanceResult (o None al invalidar)
    statusChanged = pyqtSignal(str)

    def __init__(self, image_vm: ImageViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._image_vm = image_vm
        self._f_min: float | None = None
        self._f_max: float | None = None
        self._result: ResonanceResult | None = None
        image_vm.dataChanged.connect(lambda _n: self.compute())

    @property
    def result(self) -> ResonanceResult | None:
        return self._result

    @property
    def range(self) -> tuple[float | None, float | None]:
        return self._f_min, self._f_max

    def set_range(self, f_min: float | None, f_max: float | None) -> None:
        """Rango de frecuencia (Hz) para acotar la búsqueda del pico; ``None`` = todo. Recalcula."""
        self._f_min = None if not f_min else float(f_min)
        self._f_max = None if not f_max else float(f_max)
        self.compute()

    def compute(self) -> None:
        """Extrae el espectro térmico y detecta la resonancia; emite ``resultChanged``."""
        data = self._image_vm.data
        if data is None:
            self._emit(None)
            return
        try:
            spectrum = resonance.extract_thermal(data)
            peak = resonance.find_resonance(
                spectrum.frequency, spectrum.psd, f_min=self._f_min, f_max=self._f_max
            )
        except Exception as exc:  # noqa: BLE001 - no todo .nid es de sintonía térmica
            self.statusChanged.emit(f"sintonía térmica: {exc}")
            self._emit(None)
            return
        self.statusChanged.emit(f"f0 = {peak.f0 / 1e3:.3g} kHz · Q = {peak.q_factor:.3g}")
        self._emit(
            ResonanceResult(
                frequency=np.asarray(spectrum.frequency),
                psd=np.asarray(spectrum.psd),
                peak=peak,
                reported_f0=spectrum.f0,
                reported_k=spectrum.spring_constant,
            )
        )

    def spring_constant_thermal(
        self, temperature_c: float = 20.0, correction_factor: float = 0.817
    ) -> float | None:
        """Constante de resorte ``k`` (N/m) por el método de ruido térmico (equipartición).

        Integra ``⟨x²⟩ = ∫ ASD² df`` sobre el rango activo (o todo el espectro) y aplica
        :func:`calibration.spring_constant_thermal`. Devuelve ``None`` si no hay espectro.
        Requiere que la ASD esté calibrada en m/√Hz (como en un ``.nid`` de sintonía real).
        """
        if self._result is None:
            return None
        from spmkit.core.analysis import calibration

        freq = np.asarray(self._result.frequency)
        psd = np.asarray(self._result.psd)
        mask = np.ones(freq.size, dtype=bool)
        if self._f_min is not None:
            mask &= freq >= self._f_min
        if self._f_max is not None:
            mask &= freq <= self._f_max
        if int(mask.sum()) < 2:
            return None
        variance = float(np.trapezoid(psd[mask] ** 2, freq[mask]))  # ⟨x²⟩ (m²)
        try:
            return calibration.spring_constant_thermal(
                variance,
                temperature=temperature_c + 273.15,
                correction_factor=correction_factor,
            )
        except ValueError:
            return None

    def _emit(self, result: ResonanceResult | None) -> None:
        self._result = result
        self.resultChanged.emit(result)
