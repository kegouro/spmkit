"""Panel del simulador — gemelo digital del cantiléver AFM (perspectiva Simulador).

Controles del cantiléver a la izquierda y un lienzo matplotlib con los espectros ASD
(desnudo vs. con masa) a la derecha. Reacciona a :class:`SimulatorViewModel`; el core
puro (``core.analysis.simulation``) hace la física.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.analysis import simulation
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.simulator_vm import SimulatorViewModel


class SimulatorPanel(Panel):
    """Panel central de la perspectiva Simulador."""

    title = "Simulador"

    def __init__(self, vm: SimulatorViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.resultChanged.connect(self._on_result)

    def build(self) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)

        side = QWidget()
        side.setMaximumWidth(290)
        lay = QVBoxLayout(side)
        title = QLabel("Gemelo digital")
        title.setProperty("role", "title")
        lay.addWidget(title)
        hint = QLabel(
            "Ajusta los parámetros del cantiléver y observa cómo la masa añadida "
            "desplaza la resonancia y el espectro de ruido térmico."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        lay.addWidget(hint)

        form = QFormLayout()
        p = self._vm.params
        # (etiqueta, clave SI, decimales, min, max, sufijo, factor display→SI, valor display)
        self.f0 = self._spin(form, "f₀ desnuda:", 1.0, 2000.0, " kHz", 1, p["f0_bare"] / 1e3)
        self.f0.valueChanged.connect(lambda v: self._vm.set_param("f0_bare", v * 1e3))
        self.q = self._spin(form, "Factor Q:", 1.0, 10000.0, "", 1, p["q_factor"])
        self.q.valueChanged.connect(lambda v: self._vm.set_param("q_factor", v))
        self.k = self._spin(form, "k resorte:", 0.001, 1000.0, " N/m", 4, p["spring_constant"])
        self.k.valueChanged.connect(lambda v: self._vm.set_param("spring_constant", v))
        self.dm = self._spin(form, "Δm añadida:", 0.0, 100.0, " ng", 3, p["added_mass"] * 1e12)
        self.dm.valueChanged.connect(lambda v: self._vm.set_param("added_mass", v * 1e-12))
        self.temp = self._spin(
            form, "Temperatura:", -50.0, 200.0, " °C", 1, p["temperature"] - 273.15
        )
        self.temp.valueChanged.connect(lambda v: self._vm.set_param("temperature", v + 273.15))
        lay.addLayout(form)

        self.readout = QLabel()
        self.readout.setProperty("role", "readout")
        self.readout.setWordWrap(True)
        lay.addWidget(self.readout)
        lay.addStretch(1)

        export = QPushButton("Exportar imagen…")
        export.setProperty("primary", True)
        export.clicked.connect(self._export)
        lay.addWidget(export)
        row.addWidget(side)

        self._figure = Figure(figsize=(7, 5), facecolor="white")
        self._canvas = FigureCanvasQTAgg(self._figure)
        row.addWidget(self._canvas, 1)
        return root

    def _spin(
        self,
        form: QFormLayout,
        label: str,
        lo: float,
        hi: float,
        suffix: str,
        decimals: int,
        value: float,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(lo, hi)
        spin.setSuffix(suffix)
        spin.setValue(value)
        form.addRow(label, spin)
        return spin

    def refresh(self) -> None:
        """Re-renderiza al hacerse visible (corrige el lienzo en blanco)."""
        self._vm.compute()

    # ---- reacciones ----
    def _on_result(self, result: simulation.SimulatedCantilever | None) -> None:
        if result is None:
            return
        self._draw(result)
        f0b, f0l = result.f0_bare / 1e3, result.f0_loaded / 1e3
        self.readout.setText(
            f"f₀ desnuda = {f0b:.3f} kHz\n"
            f"f₀ cargada = {f0l:.3f} kHz\n"
            f"Δf = {f0b - f0l:.3f} kHz"
        )

    def _draw(self, result: simulation.SimulatedCantilever) -> None:
        freq_khz = result.frequency / 1e3
        self._figure.clear()
        self._figure.set_facecolor("white")
        ax = self._figure.add_subplot(111)
        ax.set_facecolor("white")
        ax.plot(freq_khz, result.asd_bare * 1e12, color="#2dd4bf", lw=1.5, label="Desnudo")
        ax.plot(
            freq_khz,
            result.asd_loaded * 1e12,
            color="#ff7043",
            lw=1.5,
            ls="--",
            label="Con masa Δm",
        )
        ax.axvline(result.f0_bare / 1e3, color="#2dd4bf", lw=0.8, ls=":")
        ax.axvline(result.f0_loaded / 1e3, color="#ff7043", lw=0.8, ls=":")
        ax.set_xlabel("Frecuencia (kHz)")
        ax.set_ylabel("ASD (pm/√Hz)")
        ax.set_title(
            "Espectro de ruido térmico · La masa añadida baja la resonancia\n"
            "(equipartición: ∫ ASD² df = k_B T / k)"
        )
        ax.legend(loc="upper right")
        self._figure.tight_layout()
        self._canvas.draw()  # síncrono: evita el lienzo negro en el primer pintado

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar imagen del simulador",
            "espectro_termico.png",
            "Imágenes (*.png *.svg *.pdf)",
        )
        if path:
            self._figure.savefig(path, dpi=200, bbox_inches="tight")
