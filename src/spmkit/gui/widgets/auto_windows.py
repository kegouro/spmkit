"""Batch of calibrated NID maps with automatic, auditable physical windows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyqtgraph as pg
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.analysis.force_windows import WindowOptions
from spmkit.core.force_window_batch import WindowBatch, analyze_window_files
from spmkit.gui.runtime.tasks import Task, run_task

_ROOT = QModelIndex()


class WindowTable(QAbstractTableModel):
    headers = (
        "Archivo",
        "Curva [0…]",
        "Estado",
        "Inicio",
        "Fin incl.",
        "Frontera",
        "ΔF (nN)",
        "E (kPa)",
        "R²",
        "Motivo",
    )

    def __init__(self, result: WindowBatch, parent: QWidget) -> None:
        super().__init__(parent)
        self.result = result

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.result.rows)

    def columnCount(self, parent: QModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            return None
        r = self.result.rows[index.row()]
        w = r.window
        values = (
            r.source,
            r.curve,
            r.status,
            w.start if w else None,
            w.end if w else None,
            w.boundary if w else None,
            w.delta_force_n * 1e9 if w and w.delta_force_n is not None else None,
            w.modulus_pa * 1e-3 if w and w.modulus_pa is not None else None,
            w.r_squared if w else None,
            r.reason,
        )
        value = values[index.column()]
        return (
            format(value, ".5g")
            if isinstance(value, float)
            else str(value) if value is not None else ""
        )


class AutoWindowDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ventanas automáticas · mapas NID")
        self.resize(870, 550)
        self.task: Task | None = None
        self.batch_result: WindowBatch | None = None
        self.model: WindowTable | None = None
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.mode = QComboBox()
        self.mode.addItem("Escalones de fuerza", "steps")
        self.mode.addItem("Contacto · Hertz esférico", "contact")
        self.form.addRow("Fenómeno", self.mode)
        self.branch = QComboBox()
        self.branch.addItem("Aproximación", "extend")
        self.branch.addItem("Retracción", "retract")
        self.form.addRow("Rama", self.branch)
        self.flank = QSpinBox()
        self.flank.setRange(4, 128)
        self.flank.setValue(8)
        self.form.addRow("Muestras por lado", self.flank)
        self.sigma = self.number(3, 20, 6)
        self.form.addRow("Umbral de ruido (σ)", self.sigma)
        self.radius = self.number(0, 100000, 0)
        self.depth_input = self.number(0, 100000, 0)
        self.poisson = self.number(0, 0.499, 0.3)
        self.form.addRow("Radio de punta (nm)", self.radius)
        self.form.addRow("Indentación máxima (nm)", self.depth_input)
        self.form.addRow("Coeficiente de Poisson", self.poisson)
        row = QHBoxLayout()
        self.run_btn = QPushButton("Elegir mapas NID y analizar…")
        self.run_btn.clicked.connect(self.choose)
        self.cancel = QPushButton("Cancelar cálculo")
        self.cancel.clicked.connect(self.cancel_task)
        self.save = QPushButton("Exportar ventanas (CSV)…")
        self.save.clicked.connect(self.export)
        self.save.setEnabled(False)
        for b in (self.run_btn, self.cancel, self.save):
            row.addWidget(b)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        layout.addWidget(self.progress)
        self.table = QTableView()
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.preview = pg.PlotWidget()
        self.preview.setMinimumHeight(120)
        self.preview.setLabel("bottom", "Índice de muestra")
        self.preview.setLabel("left", "Fuerza", units="nN")
        self.preview.getAxis("left").enableAutoSIPrefix(False)
        self.preview.hide()
        layout.addWidget(self.preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self.configure)
        self.configure()
        for field in (self.radius, self.depth_input, self.poisson, self.flank, self.sigma):
            field.valueChanged.connect(self.invalidate)
        self.branch.currentIndexChanged.connect(self.invalidate)

    @staticmethod
    def number(lo: float, hi: float, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(lo, hi)
        spin.setValue(value)
        return spin

    def invalidate(self) -> None:
        self.batch_result = None
        self.preview.hide()
        self.table.setModel(None)
        if self.model is not None:
            self.model.deleteLater()
            self.model = None
        self.save.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText(
            "Los índices empiezan en 0. Contrasta los candidatos con curvas de control."
        )

    def configure(self) -> None:
        contact = self.mode.currentData() == "contact"
        self.form.setRowVisible(self.flank, not contact)
        for field in (self.radius, self.depth_input, self.poisson):
            self.form.setRowVisible(field, contact)
        if contact:
            self.branch.setCurrentIndex(0)
        self.branch.setEnabled(not contact)
        self.cancel.setEnabled(False)
        self.invalidate()

    def choose(self) -> None:
        if self.task is not None:
            return
        if (
            self.mode.currentData() == "contact"
            and min(self.radius.value(), self.depth_input.value()) <= 0
        ):
            self.status.setText(
                "Indica el radio de punta y la profundidad máxima para tu adquisición."
            )
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Mapas de fuerza para este lote", "", "Mapas Nanosurf (*.nid *.NID)"
        )
        if paths:
            self.start([Path(p) for p in paths])

    def start(self, paths: list[Path]) -> None:
        o = WindowOptions(
            self.mode.currentData(),
            self.branch.currentData(),
            self.flank.value(),
            self.sigma.value(),
            self.radius.value() or 10,
            self.poisson.value(),
            self.depth_input.value() or 5,
        )
        self.invalidate()
        self.run_btn.setEnabled(False)
        for i in range(self.form.rowCount()):
            self.form.itemAt(i, QFormLayout.ItemRole.FieldRole).widget().setEnabled(False)
        self.cancel.setEnabled(True)
        self.task = Task(analyze_window_files, paths, o, provide_progress=True)
        self.task.signals.progress.connect(self.on_progress)
        self.task.signals.done.connect(self.done_batch)
        self.task.signals.error.connect(self.on_error)
        self.task.signals.cancelled.connect(self.on_cancelled)
        self.task.signals.finished.connect(self.finish)
        run_task(self.task)

    def on_progress(self, fraction: float, message: str) -> None:
        self.progress.setValue(round(1000 * fraction))
        self.status.setText(message)

    def done_batch(self, result: WindowBatch) -> None:
        self.batch_result = result
        self.model = WindowTable(result, self)
        self.table.setModel(self.model)
        self.table.selectionModel().currentRowChanged.connect(self.show_window)
        self.save.setEnabled(bool(result.rows))
        candidates = sum(r.window is not None for r in result.rows)
        self.status.setText(
            f"{candidates} ventanas candidatas · {len(result.rows)-candidates} filas sin medición"
        )

    def show_window(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self.batch_result is None or not current.isValid():
            self.preview.hide()
            return
        row = self.batch_result.rows[current.row()]
        self.preview.clear()
        if row.preview is None:
            self.preview.hide()
            return
        self.preview.show()
        self.preview.plot(*row.preview)
        if row.window is not None:
            self.preview.addItem(
                pg.LinearRegionItem((row.window.start, row.window.end), movable=False)
            )
            self.preview.addLine(x=row.window.boundary, pen=pg.mkPen("#E38435", width=2))
        self.preview.autoRange()

    def on_error(self, exc: Exception) -> None:
        self.status.setText(str(exc))

    def on_cancelled(self) -> None:
        self.status.setText("Lote cancelado")

    def finish(self) -> None:
        self.task = None
        for i in range(self.form.rowCount()):
            self.form.itemAt(i, QFormLayout.ItemRole.FieldRole).widget().setEnabled(True)
        self.branch.setEnabled(self.mode.currentData() == "steps")
        self.run_btn.setEnabled(True)
        self.cancel.setEnabled(False)

    def cancel_task(self) -> None:
        if self.task is not None:
            self.task.cancel()

    def reject(self) -> None:
        self.cancel_task()
        super().reject()

    def export(self) -> None:
        if self.batch_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar ventanas", "ventanas.csv", "CSV (*.csv)"
        )
        if path:
            try:
                out = Path(path)
                self.batch_result.to_csv(out if out.suffix else out.with_suffix(".csv"))
                self.status.setText("CSV de ventanas guardado")
            except (OSError, ValueError) as exc:
                self.on_error(exc)
