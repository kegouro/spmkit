"""ViewModel de detección de granos — segmenta partículas sobre topografía nivelada.

Corre ``core.analysis.grains.detect`` sobre el canal **nivelado** del hub de imagen
(:class:`ImageViewModel`) con parámetros ajustables (tamaño mínimo, altura relativa).
Paridad con JPK/ANA (conteo, tamaño, cobertura, densidad de granos). Requiere scipy
(extra ``grains``); si falta, avisa por ``statusChanged`` sin tumbar la app.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.gui.viewmodels.image_vm import ImageViewModel


class GrainsViewModel(QObject):
    """Estado observable de la detección de granos."""

    resultChanged = pyqtSignal(object)  # GrainResult (o None al invalidar)
    statusChanged = pyqtSignal(str)

    def __init__(self, image_vm: ImageViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._image_vm = image_vm
        self._result: Any = None
        self._min_size = 4
        self._relative_height = 0.5
        image_vm.channelChanged.connect(lambda _n: self._invalidate())

    # ---- estado ----
    @property
    def result(self) -> Any:
        return self._result

    @property
    def min_size(self) -> int:
        return self._min_size

    @property
    def relative_height(self) -> float:
        return self._relative_height

    def base_channel(self) -> Any:
        """Canal nivelado sobre el que se detecta (para el lienzo base)."""
        return self._image_vm.current_channel()

    def set_min_size(self, value: int) -> None:
        self._min_size = max(1, int(value))

    def set_relative_height(self, value: float) -> None:
        self._relative_height = float(value)

    # ---- cálculo ----
    def detect(self) -> None:
        """Detecta granos con los parámetros actuales; emite ``resultChanged``."""
        ch = self._image_vm.current_channel()
        if ch is None:
            self.statusChanged.emit("no hay imagen cargada")
            return
        try:
            from spmkit.core.analysis import grains

            self._result = grains.detect(
                ch, min_size=self._min_size, relative_height=self._relative_height
            )
        except ImportError:
            self.statusChanged.emit("la detección de granos requiere scipy (extra 'grains')")
            return
        except Exception as exc:  # noqa: BLE001 - parámetros/imagen inválidos: se informa
            self.statusChanged.emit(f"detección falló: {exc}")
            return
        self.statusChanged.emit(f"{self._result.n_grains} grano(s) detectado(s)")
        self.resultChanged.emit(self._result)

    def _invalidate(self) -> None:
        self._result = None
        self.resultChanged.emit(None)
