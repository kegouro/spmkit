"""ViewModel del simulador — gemelo digital del cantiléver AFM.

Estado observable de la simulación del espectro de ruido térmico (SHO): guarda los
parámetros del cantiléver en SI y recalcula al vuelo con ``core.analysis.simulation``.
La perspectiva de fuerza sigue siendo la joya; esto es didáctico.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import simulation

#: Parámetros por defecto (SI): f₀=75 kHz, Q=100, k=1 N/m, Δm=1 ng, T=20 °C.
DEFAULT_PARAMS: dict[str, float] = {
    "f0_bare": 75e3,
    "q_factor": 100.0,
    "spring_constant": 1.0,
    "added_mass": 1e-12,
    "temperature": 293.15,
}


class SimulatorViewModel(QObject):
    """Estado observable del simulador de cantiléver."""

    resultChanged = pyqtSignal(object)  # SimulatedCantilever (o None si el ajuste es inválido)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._params = dict(DEFAULT_PARAMS)
        self._result: simulation.SimulatedCantilever | None = None

    @property
    def params(self) -> dict[str, float]:
        return dict(self._params)

    @property
    def result(self) -> simulation.SimulatedCantilever | None:
        return self._result

    def set_param(self, name: str, value: float) -> None:
        """Actualiza un parámetro (SI) y recalcula si cambió."""
        if name not in self._params or self._params[name] == value:
            return
        self._params[name] = value
        self.compute()

    def compute(self) -> None:
        """Recalcula la simulación; emite ``resultChanged`` (``None`` si es inválida)."""
        p = self._params
        try:
            self._result = simulation.simulate(
                f0_bare=p["f0_bare"],
                q_factor=p["q_factor"],
                spring_constant=p["spring_constant"],
                added_mass=p["added_mass"],
                temperature=p["temperature"],
            )
        except ValueError:
            self._result = None
        self.resultChanged.emit(self._result)
