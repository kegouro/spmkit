"""Pestaña Resonancia: sensado de masa por evaporación (thermal tuning).

Carga una carpeta de espectros de *thermal tuning* (.nid) tomados a lo largo
del tiempo y muestra los espectros, la frecuencia de resonancia f(t), la masa
añadida Δm(t) y la tasa de evaporación dΔm/dt.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
from PyQt6 import QtWidgets

from spmkit import load
from spmkit.core.analysis import resonance
from spmkit.core.models import SPMData


class ResonanceTab(QtWidgets.QWidget):
    """Análisis de resonancia y masa durante una evaporación."""

    def __init__(self) -> None:
        super().__init__()
        self._spectra: list = []
        self._build()

    def _build(self) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QtWidgets.QHBoxLayout(self)

        side = QtWidgets.QWidget()
        side.setMaximumWidth(290)
        lay = QtWidgets.QVBoxLayout(side)
        title = QtWidgets.QLabel("Resonancia · masa")
        title.setProperty("role", "title")
        lay.addWidget(title)
        hint = QtWidgets.QLabel(
            "Carga una carpeta con espectros de thermal tuning (.nid) tomados en el tiempo."
        )
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        load_btn = QtWidgets.QPushButton("Cargar carpeta…")
        load_btn.setProperty("primary", True)
        load_btn.clicked.connect(self._load_folder)
        lay.addWidget(load_btn)

        form = QtWidgets.QFormLayout()
        self.k_spin = QtWidgets.QDoubleSpinBox()
        self.k_spin.setDecimals(4)
        self.k_spin.setRange(0.0, 1000.0)
        self.k_spin.setSuffix(" N/m")
        self.k_spin.valueChanged.connect(self._recompute)
        form.addRow("k(L) extremo:", self.k_spin)
        self.xl_spin = QtWidgets.QDoubleSpinBox()
        self.xl_spin.setDecimals(3)
        self.xl_spin.setRange(0.05, 1.0)
        self.xl_spin.setSingleStep(0.05)
        self.xl_spin.setValue(1.0)
        self.xl_spin.setToolTip("Posición de carga x/L (micrografía). k(x)=k(L)/(x/L)³")
        self.xl_spin.valueChanged.connect(self._recompute)
        form.addRow("posición x/L:", self.xl_spin)
        lay.addLayout(form)

        self.summary = QtWidgets.QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setProperty("role", "readout")
        lay.addWidget(self.summary)
        export = QtWidgets.QPushButton("Exportar CSV…")
        export.clicked.connect(self._export)
        lay.addWidget(export)
        anim_btn = QtWidgets.QPushButton("Exportar animación…")
        anim_btn.clicked.connect(self._export_animation)
        lay.addWidget(anim_btn)
        root.addWidget(side)

        self.canvas = FigureCanvasQTAgg(Figure(figsize=(8, 6)))
        root.addWidget(self.canvas, stretch=1)

    # ---------------------------------------------------------------- API
    def set_data(self, data: SPMData | None) -> None:
        """Gestiona su propia carpeta; ignora el archivo activo del shell."""

    def refresh(self) -> None:
        """Re-renderiza al hacerse visible (corrige el lienzo en blanco)."""
        if self._spectra:
            self._recompute()

    # ------------------------------------------------------------ carga
    def _load_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Carpeta de thermal tuning")
        if not folder:
            return
        files = sorted(Path(folder).glob("*.nid"))
        if len(files) < 2:
            QtWidgets.QMessageBox.information(
                self, "Resonancia", "La carpeta necesita al menos 2 espectros .nid."
            )
            return
        try:
            spectra = [resonance.extract_thermal(load(f)) for f in files]
            spectra = [s for s in spectra if s.timestamp is not None]
            spectra.sort(key=lambda s: s.timestamp or datetime.min)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return
        self._spectra = spectra
        k = spectra[0].spring_constant
        self.k_spin.blockSignals(True)
        self.k_spin.setValue(k if np.isfinite(k) else 1.0)
        self.k_spin.blockSignals(False)
        self._recompute()

    def _series(self) -> resonance.EvaporationSeries | None:
        if len(self._spectra) < 2:
            return None
        t0 = self._spectra[0].timestamp or datetime.min
        times = np.array(
            [((s.timestamp or datetime.min) - t0).total_seconds() for s in self._spectra]
        )
        freqs = np.array([s.f0 for s in self._spectra])
        return resonance.track_evaporation(
            times, freqs, self.k_spin.value(), x_over_l=self.xl_spin.value()
        )

    # ------------------------------------------------------------ render
    def _recompute(self) -> None:
        ev = self._series()
        if ev is None:
            return
        fig = self.canvas.figure
        fig.clear()
        axes = fig.subplots(2, 2)
        th = self._spectra

        # 1) espectros coloreados por tiempo
        ax = axes[0][0]
        import matplotlib.cm as cm

        n = len(th)
        for i, s in enumerate(th):
            ax.plot(s.frequency / 1e3, s.psd * 1e12, color=cm.viridis(i / max(1, n - 1)), lw=0.8)
        ax.set_xlabel("Frecuencia (kHz)")
        ax.set_ylabel("ASD (pm/√Hz)")
        ax.set_title("Espectros (color = tiempo)")

        # 2) f(t)
        ax = axes[0][1]
        ax.plot(ev.time / 3600, ev.frequency / 1e3, "o-", color="#2dd4bf")
        ax.axhline(ev.bare_frequency / 1e3, ls="--", color="gray", lw=1)
        ax.set_xlabel("Tiempo (h)")
        ax.set_ylabel("f₀ (kHz)")
        ax.set_title("Resonancia vs tiempo")

        # 3) Δm(t)
        ax = axes[1][0]
        ax.plot(ev.time / 3600, ev.added_mass * 1e12, "o-", color="#4ea1ff")
        ax.set_xlabel("Tiempo (h)")
        ax.set_ylabel("Δm (ng)")
        ax.set_title("Masa añadida")

        # 4) tasa de evaporación
        ax = axes[1][1]
        ax.plot(ev.time / 3600, ev.evaporation_rate * 1e12 * 3600, "o-", color="#ffb454")
        ax.axhline(0, ls=":", color="gray", lw=1)
        ax.set_xlabel("Tiempo (h)")
        ax.set_ylabel("dΔm/dt (ng/h)")
        ax.set_title("Tasa de evaporación")

        fig.tight_layout()
        self.canvas.draw_idle()

        # Ajuste ley d²
        radios = resonance.droplet_radius(ev.added_mass)
        d2 = resonance.fit_d2_law(ev.time, radios)
        tau_h = d2.tau / 3600.0 if np.isfinite(d2.tau) else float("inf")
        K_um2_s = d2.rate_constant * 1e12  # m²/s → µm²/s
        r0_um = d2.r0 * 1e6  # m → µm
        diff_str = "Sí" if d2.is_diffusion_limited else "No"

        self.summary.setHtml(
            f"<b>Resultados</b><br>"
            f"k = {ev.spring_constant:.4g} N/m<br>"
            f"f₀ desnuda = {ev.bare_frequency / 1e3:.2f} kHz<br>"
            f"Δm inicial = {ev.added_mass[0] * 1e12:.3f} ng<br>"
            f"masa evaporada = {(ev.added_mass[0] - ev.added_mass[-1]) * 1e12:.3f} ng<br>"
            f"puntos = {len(ev.time)}<br>"
            f"<br><b>Ley d² (evaporación)</b><br>"
            f"r₀ = {r0_um:.2f} µm<br>"
            f"τ = {tau_h:.2f} h<br>"
            f"K = {K_um2_s:.4g} µm²/s<br>"
            f"R² = {d2.r_squared:.4f}<br>"
            f"Difusión limitada: {diff_str}"
        )

    def _export_animation(self) -> None:
        if len(self._spectra) < 2:
            QtWidgets.QMessageBox.information(
                self, "Animación", "Carga primero una serie de espectros."
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar animación GIF", "evaporacion.gif", "GIF (*.gif)"
        )
        if not path:
            return
        try:
            out = resonance.animate_evaporation(self._spectra, path)
            QtWidgets.QMessageBox.information(self, "Animación", f"GIF guardado en:\n{out}")
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error al animar", str(exc))

    def _export(self) -> None:
        ev = self._series()
        if ev is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar CSV", "evaporacion.csv")
        if not path:
            return
        import csv as _csv

        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["time_s", "frequency_Hz", "mass_kg", "added_mass_kg", "evap_rate_kg_s"])
            for i in range(len(ev.time)):
                w.writerow(
                    [
                        ev.time[i],
                        ev.frequency[i],
                        ev.mass[i],
                        ev.added_mass[i],
                        ev.evaporation_rate[i],
                    ]
                )
