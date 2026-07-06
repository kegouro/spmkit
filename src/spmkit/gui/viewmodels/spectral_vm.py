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
        image_vm.channelChanged.connect(lambda _n: self.compute())

    @property
    def result(self) -> SpectralResult | None:
        return self._result

    def compute(self) -> None:
        """Calcula PSD + fractal + correlación del canal activo; emite ``resultChanged``."""
        ch = self._image_vm.current_channel()
        if ch is None:
            self._emit(None)
            return
        try:
            result = SpectralResult(
                psd=spectral.radial_psd(ch),
                fractal=spectral.fractal_dimension(ch),
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
