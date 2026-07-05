"""Panel de pipeline en vivo — el ancla de diferenciación del rediseño.

Edita los parámetros del ajuste (modelo de contacto, geometría de punta, Poisson,
calibración) y reconstruye la :class:`Recipe`; el :class:`ForceViewModel` la re-ejecuta
con debounce y el lienzo/inspector se actualizan al instante. Es lo que ANA/JPK hacen
en diálogos modales, aquí en vivo y siempre visible.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ForceViewModel

#: Modelos de contacto: valor interno → etiqueta visible.
_MODELS: tuple[tuple[str, str], ...] = (
    ("sphere", "Hertz esférico"),
    ("paraboloid", "Paraboloide"),
    ("cone", "Sneddon cónico"),
    ("dmt", "DMT (adhesivo)"),
)


class PipelinePanel(Panel):
    """Panel-dock con los controles del pipeline de ajuste (edición en vivo)."""

    title = "Pipeline"

    def __init__(self, vm: ForceViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        self._building = True
        super().__init__(parent)
        self._building = False

    def build(self) -> QWidget:
        root = QWidget()
        outer = QVBoxLayout(root)
        heading = QLabel("Pipeline de ajuste")
        heading.setProperty("role", "title")
        outer.addWidget(heading)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)

        self._model = QComboBox()
        for value, label in _MODELS:
            self._model.addItem(label, value)
        self._model.currentIndexChanged.connect(self._on_model_changed)
        form.addRow("Modelo", self._model)

        self._radius = self._spin(0.1, 100000.0, 10.0, " nm", 1)
        form.addRow("Radio de punta", self._radius)

        self._angle = self._spin(1.0, 89.0, 20.0, " °", 1)
        form.addRow("Semiángulo", self._angle)

        self._poisson = self._spin(0.0, 0.5, 0.3, "", 2, step=0.05)
        form.addRow("Poisson ν", self._poisson)

        cal = QLabel("Calibración (0 = usar metadatos del archivo)")
        cal.setProperty("role", "muted")
        outer.addLayout(form)
        outer.addWidget(cal)

        cal_form = QFormLayout()
        cal_form.setHorizontalSpacing(16)
        self._invols = self._spin(0.0, 100000.0, 0.0, " nm/V", 2)
        cal_form.addRow("InVOLS", self._invols)
        self._k = self._spin(0.0, 1000.0, 0.0, " N/m", 3)
        cal_form.addRow("k resorte", self._k)
        outer.addLayout(cal_form)
        outer.addStretch(1)

        self._update_enabled()
        return root

    def _spin(
        self,
        lo: float,
        hi: float,
        value: float,
        suffix: str,
        decimals: int,
        step: float | None = None,
    ) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(lo, hi)
        box.setDecimals(decimals)
        box.setValue(value)
        box.setSuffix(suffix)
        if step is not None:
            box.setSingleStep(step)
        box.valueChanged.connect(self._apply)
        return box

    # ---- lógica ----
    def _on_model_changed(self, _idx: int) -> None:
        self._update_enabled()
        self._apply()

    def _update_enabled(self) -> None:
        is_cone = self._model.currentData() == "cone"
        self._angle.setEnabled(is_cone)
        self._radius.setEnabled(not is_cone)

    def _apply(self, *_args: object) -> None:
        """Empuja todos los controles a los parámetros del ViewModel (un re-ajuste)."""
        if self._building:
            return
        self._vm.set_params(
            model=self._model.currentData(),
            tip_radius=self._radius.value() * 1e-9,
            poisson=self._poisson.value(),
            half_angle=math.radians(self._angle.value()),
            invols=(self._invols.value() * 1e-9) or None,
            spring_constant=self._k.value() or None,
        )
