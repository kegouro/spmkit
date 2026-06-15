"""Pestaña Simulador: gemelo digital educativo del cantiléver AFM.

Demuestra cómo el espectro de ruido térmico (ASD) y la frecuencia de
resonancia se desplazan al añadir masa en la punta — conectado con el
experimento de evaporación de *liquid marbles*.

Física: oscilador armónico simple (SHO); normalización por equipartición.
El core está en ``spmkit.core.analysis.simulation``.
"""

from __future__ import annotations

from PyQt6 import QtWidgets

from spmkit.core.analysis import simulation


class SimulatorTab(QtWidgets.QWidget):
    """Simulador interactivo del espectro térmico del cantiléver.

    Panel izquierdo con controles (``QDoubleSpinBox``) y un ``FigureCanvasQTAgg``
    a la derecha que muestra el espectro ASD desnudo y cargado en tiempo real.
    """

    def __init__(self) -> None:
        super().__init__()
        self._build()
        self._recompute()

    # ---------------------------------------------------------------- build

    def _build(self) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QtWidgets.QHBoxLayout(self)

        # ---------- panel izquierdo ≤ 290 px ----------
        side = QtWidgets.QWidget()
        side.setMaximumWidth(290)
        lay = QtWidgets.QVBoxLayout(side)

        title = QtWidgets.QLabel("Gemelo digital")
        title.setProperty("role", "title")
        lay.addWidget(title)

        hint = QtWidgets.QLabel(
            "Ajusta los parámetros del cantiléver y observa cómo la masa añadida "
            "desplaza la resonancia y el espectro de ruido térmico."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        lay.addWidget(hint)

        # --- controles ---
        form = QtWidgets.QFormLayout()

        self.f0_spin = QtWidgets.QDoubleSpinBox()
        self.f0_spin.setDecimals(1)
        self.f0_spin.setRange(1.0, 2000.0)
        self.f0_spin.setSuffix(" kHz")
        self.f0_spin.setValue(75.0)
        self.f0_spin.valueChanged.connect(self._recompute)
        form.addRow("f₀ desnuda:", self.f0_spin)

        self.q_spin = QtWidgets.QDoubleSpinBox()
        self.q_spin.setDecimals(1)
        self.q_spin.setRange(1.0, 10000.0)
        self.q_spin.setValue(100.0)
        self.q_spin.valueChanged.connect(self._recompute)
        form.addRow("Factor Q:", self.q_spin)

        self.k_spin = QtWidgets.QDoubleSpinBox()
        self.k_spin.setDecimals(4)
        self.k_spin.setRange(0.001, 1000.0)
        self.k_spin.setSuffix(" N/m")
        self.k_spin.setValue(1.0)
        self.k_spin.valueChanged.connect(self._recompute)
        form.addRow("k resorte:", self.k_spin)

        self.dm_spin = QtWidgets.QDoubleSpinBox()
        self.dm_spin.setDecimals(3)
        self.dm_spin.setRange(0.0, 100.0)
        self.dm_spin.setSuffix(" ng")
        self.dm_spin.setValue(1.0)
        self.dm_spin.valueChanged.connect(self._recompute)
        form.addRow("Δm añadida:", self.dm_spin)

        self.temp_spin = QtWidgets.QDoubleSpinBox()
        self.temp_spin.setDecimals(1)
        self.temp_spin.setRange(-50.0, 200.0)
        self.temp_spin.setSuffix(" °C")
        self.temp_spin.setValue(20.0)
        self.temp_spin.valueChanged.connect(self._recompute)
        form.addRow("Temperatura:", self.temp_spin)

        lay.addLayout(form)

        # --- label de resultados ---
        self.readout = QtWidgets.QLabel()
        self.readout.setProperty("role", "readout")
        self.readout.setWordWrap(True)
        lay.addWidget(self.readout)

        lay.addStretch()

        # --- botón exportar ---
        export_btn = QtWidgets.QPushButton("Exportar imagen…")
        export_btn.setProperty("primary", True)
        export_btn.clicked.connect(self._export)
        lay.addWidget(export_btn)

        root.addWidget(side)

        # ---------- canvas matplotlib ----------
        self._figure = Figure(figsize=(7, 5))
        self.canvas = FigureCanvasQTAgg(self._figure)
        root.addWidget(self.canvas, stretch=1)

    # ---------------------------------------------------------------- API

    def set_data(self, data: object) -> None:  # noqa: ARG002
        """No-op: el simulador no usa datos de archivo."""

    # ---------------------------------------------------------------- lógica

    def _recompute(self) -> None:
        """Recalcula la simulación con los valores actuales y actualiza el plot."""
        f0_hz = self.f0_spin.value() * 1e3  # kHz → Hz
        q = self.q_spin.value()
        k = self.k_spin.value()
        dm_kg = self.dm_spin.value() * 1e-12  # ng → kg
        temp_k = self.temp_spin.value() + 273.15  # °C → K

        try:
            result = simulation.simulate(
                f0_bare=f0_hz,
                q_factor=q,
                spring_constant=k,
                added_mass=dm_kg,
                temperature=temp_k,
            )
        except ValueError:
            return

        self._draw(result)

        # Actualizar label de resultados
        f0b_khz = result.f0_bare / 1e3
        f0l_khz = result.f0_loaded / 1e3
        df_khz = f0b_khz - f0l_khz
        self.readout.setText(
            f"f₀ desnuda = {f0b_khz:.3f} kHz\n"
            f"f₀ cargada = {f0l_khz:.3f} kHz\n"
            f"Δf = {df_khz:.3f} kHz"
        )

    def _draw(self, result: simulation.SimulatedCantilever) -> None:
        """Dibuja los dos espectros ASD en el canvas matplotlib."""
        freq_khz = result.frequency / 1e3
        asd_bare_pm = result.asd_bare * 1e12  # m/√Hz → pm/√Hz
        asd_loaded_pm = result.asd_loaded * 1e12

        self._figure.clear()
        ax = self._figure.add_subplot(111)

        ax.plot(freq_khz, asd_bare_pm, color="#2dd4bf", lw=1.5, label="Desnudo")
        ax.plot(freq_khz, asd_loaded_pm, color="#ff7043", lw=1.5, ls="--", label="Con masa Δm")

        # Líneas verticales en cada resonancia
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
        self.canvas.draw_idle()

    # ---------------------------------------------------------------- exportar

    def _export(self) -> None:
        """Exporta la figura actual a una imagen."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar imagen del simulador",
            "espectro_termico.png",
            "Imágenes (*.png *.svg *.pdf)",
        )
        if path:
            self._figure.savefig(path, dpi=200, bbox_inches="tight")
