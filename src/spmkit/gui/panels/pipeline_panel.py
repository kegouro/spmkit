"""Panel de pipeline en vivo — el ancla de diferenciación del rediseño.

Edita los parámetros del ajuste (modelo de contacto, geometría de punta, Poisson,
calibración) y reconstruye la :class:`Recipe`; el :class:`ForceViewModel` la re-ejecuta
con debounce y el lienzo/inspector se actualizan al instante. Es lo que ANA/JPK hacen
en diálogos modales, aquí en vivo y siempre visible.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
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

#: Métodos de detección del punto de contacto: valor interno → etiqueta visible.
_CONTACT_METHODS: tuple[tuple[str, str], ...] = (
    ("joint", "Conjunto (robusto)"),
    ("threshold", "Umbral k·σ"),
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

        self._smooth = self._spin(0.0, 99.0, 0.0, " pts", 0, step=2.0)
        self._smooth.setToolTip("Suavizado Savitzky-Golay antes del ajuste (0 = ninguno)")
        form.addRow("Suavizado", self._smooth)

        self._contact = QComboBox()
        for value, label in _CONTACT_METHODS:
            self._contact.addItem(label, value)
        self._contact.setToolTip(
            "Detección del punto de contacto. 'Conjunto' es inmune al sesgo de módulo (~+30%)\n"
            "que el umbral introduce bajo ruido."
        )
        self._contact.currentIndexChanged.connect(self._apply)
        form.addRow("Contacto", self._contact)

        self._ksigma = self._spin(1.0, 15.0, 5.0, " σ", 1, step=0.5)
        self._ksigma.setToolTip("Umbral de ruido de la detección de contacto (múltiplos de σ)")
        form.addRow("k·σ (umbral)", self._ksigma)

        cal = QLabel("Calibración (0 = usar metadatos del archivo)")
        cal.setProperty("role", "muted")
        outer.addLayout(form)
        outer.addWidget(cal)

        cal_form = QFormLayout()
        cal_form.setHorizontalSpacing(16)
        self._invols = self._spin(0.0, 100000.0, 0.0, " nm/V", 2)
        invols_row = QWidget()
        ir = QHBoxLayout(invols_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.addWidget(self._invols, 1)
        calc = QPushButton("Calcular")
        calc.setToolTip("Estima el InVOLS de la zona de contacto de la curva activa.")
        calc.clicked.connect(self._calc_invols)
        ir.addWidget(calc)
        cal_form.addRow("InVOLS", invols_row)
        self._k = self._spin(0.0, 1000.0, 0.0, " N/m", 3)
        cal_form.addRow("k resorte", self._k)
        outer.addLayout(cal_form)

        self._mc = QCheckBox("Incertidumbre Monte Carlo (± módulo)")
        self._mc.setToolTip("Propaga los errores relativos de InVOLS y k al módulo de Young.")
        self._mc.toggled.connect(self._on_mc_toggled)
        outer.addWidget(self._mc)

        mc_form = QFormLayout()
        mc_form.setHorizontalSpacing(16)
        self._invols_err = self._spin(0.0, 0.5, 0.05, "", 3, step=0.01)
        mc_form.addRow("Error rel. InVOLS", self._invols_err)
        self._k_err = self._spin(0.0, 0.5, 0.05, "", 3, step=0.01)
        mc_form.addRow("Error rel. k", self._k_err)
        self._mc_n = QSpinBox()
        self._mc_n.setRange(10, 2000)
        self._mc_n.setValue(200)
        self._mc_n.valueChanged.connect(self._apply)
        mc_form.addRow("Muestras MC", self._mc_n)
        self._mc_seed = QSpinBox()
        self._mc_seed.setRange(0, 999999)
        self._mc_seed.setValue(0)
        self._mc_seed.setToolTip("Semilla del Monte Carlo (reproducibilidad)")
        self._mc_seed.valueChanged.connect(self._apply)
        mc_form.addRow("Semilla MC", self._mc_seed)
        outer.addLayout(mc_form)
        outer.addStretch(1)

        self._update_enabled()
        self._on_mc_toggled(False)
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

    def _on_mc_toggled(self, checked: bool) -> None:
        for w in (self._invols_err, self._k_err, self._mc_n, self._mc_seed):
            w.setEnabled(checked)
        self._apply()

    def _calc_invols(self) -> None:
        """Estima el InVOLS de la curva activa y lo escribe en el control (m/V → nm/V)."""
        invols = self._vm.estimate_invols()
        if invols is not None:
            self._invols.setValue(invols * 1e9)  # el valueChanged dispara el re-ajuste

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
            smooth_window=int(self._smooth.value()),
            contact_method=self._contact.currentData(),
            k_sigma=self._ksigma.value(),
            mc=self._mc.isChecked(),
            invols_rel_err=self._invols_err.value(),
            k_rel_err=self._k_err.value(),
            mc_samples=int(self._mc_n.value()),
            mc_seed=int(self._mc_seed.value()),
        )
