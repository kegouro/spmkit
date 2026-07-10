"""ViewModel de análisis espectral — PSD radial, dimensión fractal, correlación.

Corre ``core.analysis.spectral`` sobre el canal nivelado del hub de imagen
(:class:`ImageViewModel`): PSD radialmente promediada + exponente de Hurst / dimensión
fractal + longitud de correlación. Barato (FFT), así que recalcula al cambiar de canal.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import spectral
from spmkit.gui.viewmodels.image_vm import ImageViewModel


@dataclass(frozen=True)
class SpectralResult:
    """Agregado de los tres análisis espectrales de un canal."""

    psd: spectral.RadialPSD
    fractal: spectral.FractalResult
    correlation_length: float


class SpectralViewModel(QObject):
    """Estado observable del análisis espectral."""

    resultChanged = pyqtSignal(object)  # SpectralResult (o None al invalidar)
    statusChanged = pyqtSignal(str)

    def __init__(self, image_vm: ImageViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._image_vm = image_vm
        self._result: SpectralResult | None = None
        self._q_min: float | None = None  # 1/m; rango de ajuste fractal (None = auto)
        self._q_max: float | None = None
        image_vm.channelChanged.connect(lambda _n: self.compute())

    @property
    def result(self) -> SpectralResult | None:
        return self._result

    @property
    def q_range(self) -> tuple[float | None, float | None]:
        return self._q_min, self._q_max

    def set_q_range(self, q_min: float | None, q_max: float | None) -> None:
        """Rango de frecuencias del ajuste fractal (1/m); ``None`` = automático. Recalcula."""
        self._q_min = None if not q_min else float(q_min)
        self._q_max = None if not q_max else float(q_max)
        self.compute()

    def compute(self) -> None:
        """Calcula PSD + fractal + correlación del canal activo; emite ``resultChanged``."""
        ch = self._image_vm.current_channel()
        if ch is None:
            self._emit(None)
            return
        try:
            result = SpectralResult(
                psd=spectral.radial_psd(ch),
                fractal=spectral.fractal_dimension(ch, q_min=self._q_min, q_max=self._q_max),
                correlation_length=spectral.correlation_length(ch),
            )
        except Exception as exc:  # noqa: BLE001 - canal degenerado: se informa, no tumba
            self.statusChanged.emit(f"análisis espectral falló: {exc}")
            self._emit(None)
            return
        self._emit(result)

    def _emit(self, result: SpectralResult | None) -> None:
        self._result = result
        self.resultChanged.emit(result)
