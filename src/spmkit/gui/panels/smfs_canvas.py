"""Panel SMFS — retract + eventos de ruptura + ajustes de cadena (perspectiva SMFS).

Dibuja la rama de retracción corregida (fuerza vs separación), marca las rupturas detectadas
en oro de marca, superpone el ajuste WLC/FJC de cada evento en teal y lista contorno,
persistencia/Kuhn y R² en una tabla. Reacciona a :class:`SmfsViewModel` (recalcula al cambiar
de curva o de modelo). Un selector conmuta el modelo de cadena.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.design import tokens
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.smfs_vm import SmfsResult, SmfsViewModel

_NM = 1e9  # m → nm
_NN = 1e9  # N → nN


class SmfsCanvasPanel(Panel):
    """Panel central de la perspectiva SMFS."""

    title = "SMFS"

    def __init__(self, vm: SmfsViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.resultChanged.connect(self._on_result)
        self._on_result(vm.result)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        controls = QWidget()
        crow = QHBoxLayout(controls)
        crow.setContentsMargins(0, 0, 0, 0)
        crow.addWidget(QLabel("Modelo de cadena:"))
        self._combo = QComboBox()
        self._combo.addItem("WLC", "wlc")
        self._combo.addItem("FJC (Langevin)", "fjc")
        self._combo.currentIndexChanged.connect(self._on_model_changed)
        crow.addWidget(self._combo)

        self._wlc_combo = QComboBox()
        self._wlc_combo.addItem("Bouchiat", "bouchiat")
        self._wlc_combo.addItem("Marko-Siggia", "marko_siggia")
        self._wlc_combo.setToolTip("Variante del WLC (Bouchiat es más preciso cerca de L)")
        self._wlc_combo.currentIndexChanged.connect(
            lambda _i: self._vm.set_wlc_model(self._wlc_combo.currentData())
        )
        crow.addWidget(self._wlc_combo)

        self._readout = QLabel("<i>Sin eventos (carga una curva de fuerza)</i>")
        self._readout.setProperty("role", "readout")
        crow.addWidget(self._readout, 1)
        lay.addWidget(controls)

        # Umbrales del pipeline editables (nada hardcodeado): QC y detección.
        params = QWidget()
        prow = QHBoxLayout(params)
        prow.setContentsMargins(0, 0, 0, 0)
        p = self._vm.params
        self._spins: dict[str, QDoubleSpinBox] = {}
        prow.addWidget(self._spin("min_r_squared", "R² mínimo", 0.0, 1.0, 0.01, 2, p))
        prow.addWidget(self._spin("min_prominence_sigma", "Prominencia (σ)", 1.0, 30.0, 0.5, 1, p))
        prow.addWidget(self._spin("min_height_sigma", "Altura (σ)", 1.0, 30.0, 0.5, 1, p))
        prow.addWidget(self._spin("baseline_fraction", "Cola base", 0.05, 0.6, 0.05, 2, p))

        temp_box = QWidget()
        trow = QHBoxLayout(temp_box)
        trow.setContentsMargins(0, 0, 0, 0)
        trow.setSpacing(4)
        trow.addWidget(QLabel("Temp (°C)"))
        self._temp = QDoubleSpinBox()
        self._temp.setRange(-50.0, 200.0)
        self._temp.setDecimals(1)
        self._temp.setValue(p["temperature"] - 273.15)  # K → °C
        self._temp.valueChanged.connect(lambda c: self._vm.set_param("temperature", c + 273.15))
        trow.addWidget(self._temp)
        prow.addWidget(temp_box)

        prow.addStretch(1)
        lay.addWidget(params)
        self._update_wlc_enabled()

        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Separación", units="nm")
        self._plot.setLabel("left", "Fuerza", units="nN")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        lay.addWidget(self._plot, 1)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "Contorno (nm)", "lp (nm)", "R²"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setMaximumHeight(180)
        lay.addWidget(self._table)
        return root

    def _on_model_changed(self, _idx: int) -> None:
        self._vm.set_model(self._combo.currentData())
        self._update_wlc_enabled()

    def _update_wlc_enabled(self) -> None:
        """La variante WLC solo aplica al modelo WLC."""
        self._wlc_combo.setEnabled(self._combo.currentData() == "wlc")

    def _spin(
        self,
        key: str,
        label: str,
        lo: float,
        hi: float,
        step: float,
        decimals: int,
        params: dict[str, float],
    ) -> QWidget:
        """Control etiquetado (QDoubleSpinBox) cableado a ``vm.set_param(key, …)``."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(QLabel(label))
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setValue(params[key])
        spin.valueChanged.connect(lambda v, k=key: self._vm.set_param(k, v))
        self._spins[key] = spin
        row.addWidget(spin)
        return box

    def _on_result(self, result: SmfsResult | None) -> None:
        import pyqtgraph as pg

        self._plot.clear()
        self._table.setRowCount(0)
        if result is None:
            self._readout.setText("<i>Sin eventos (carga una curva de fuerza)</i>")
            return

        self._plot.plot(
            result.separation * _NM,
            result.force * _NN,
            pen=pg.mkPen(tokens.TRACES["retract"], width=1.2),
        )
        for osep, oforce in result.overlays:
            self._plot.plot(
                np.asarray(osep) * _NM,
                np.asarray(oforce) * _NN,
                pen=pg.mkPen(tokens.TRACES["fit"], width=2.2),
            )
        if result.events:
            peaks = pg.ScatterPlotItem(
                [ef.event.separation * _NM for ef in result.events],
                [ef.event.force * _NN for ef in result.events],
                size=11,
                brush=tokens.TRACES["contact"],
                pen=pg.mkPen("#1b2430", width=1.0),
            )
            self._plot.addItem(peaks)

        n = len(result.events)
        plural = "s" if n != 1 else ""
        self._readout.setText(f"<b>{n} evento{plural}</b> — modelo {result.model.upper()}")
        self._fill_table(result)

    def _fill_table(self, result: SmfsResult) -> None:
        is_wlc = result.model == "wlc"
        self._table.setHorizontalHeaderLabels(
            ["#", "Contorno (nm)", "lp (nm)" if is_wlc else "b (nm)", "R²"]
        )
        self._table.setRowCount(len(result.events))
        for i, ef in enumerate(result.events):
            fit = ef.fit
            second = fit.persistence_length if is_wlc else (fit.kuhn_length or 0.0)
            values = (
                str(i + 1),
                f"{fit.contour_length * _NM:.1f}",
                f"{second * _NM:.2f}",
                f"{fit.r_squared:.3f}",
            )
            for col, text in enumerate(values):
                self._table.setItem(i, col, QTableWidgetItem(text))
