"""Tabla de procesamiento por lotes — reemplaza el batch de ANA/JPK.

Corre la receta activa sobre una carpeta de curvas (``.jpk-force``/``.nid``) y muestra
una fila por archivo con módulo, adhesión y disipación medianos. Exporta a CSV. El
cómputo pesado va fuera del hilo de UI (barra de progreso cancelable en el shell).
"""

from __future__ import annotations

import math
from csv import Error as CsvError
from pathlib import Path

from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.forcebatch import ForceBatchResult, ForceBatchRow
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import BatchViewModel

_HEADERS = (
    "Archivo",
    "Curvas",
    "Procesadas",
    "E med (kPa)",
    "E σ (kPa)",
    "Adh (nN)",
    "Disip (fJ)",
    "Curvas fallidas",
    "n E",
    "n Adh",
    "n Disip",
    "Error",
)


def _fmt(value: float, scale: float) -> str:
    return "—" if not math.isfinite(value) else f"{value * scale:.3g}"


def _row_items(row: ForceBatchRow) -> list[QStandardItem]:
    return [
        QStandardItem(row.source),
        QStandardItem(str(row.n_curves)),
        QStandardItem(str(row.n_ok)),
        QStandardItem(_fmt(row.young_modulus_median, 1e-3)),
        QStandardItem(_fmt(row.young_modulus_std, 1e-3)),
        QStandardItem(_fmt(row.adhesion_median, 1e9)),
        QStandardItem(_fmt(row.dissipation_median, 1e15)),
        QStandardItem(str(row.n_curves_failed)),
        QStandardItem(str(row.n_young_modulus)),
        QStandardItem(str(row.n_adhesion)),
        QStandardItem(str(row.n_dissipation)),
        QStandardItem(row.error),
    ]


class BatchTablePanel(Panel):
    """Panel central de la perspectiva batch: carpeta → tabla resumen + export CSV."""

    title = "Batch"

    def __init__(self, batch_vm: BatchViewModel, parent: QWidget | None = None) -> None:
        self._vm = batch_vm
        super().__init__(parent)
        batch_vm.batchReady.connect(self._on_batch_ready)
        batch_vm.computingChanged.connect(self._on_computing)
        batch_vm.statusChanged.connect(self._show_status)

    def build(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        self._open_btn = QPushButton("Abrir carpeta…")
        self._open_btn.setProperty("primary", "true")
        self._open_btn.clicked.connect(self._choose_folder)
        self._export_btn = QPushButton("Exportar CSV…")
        self._export_btn.clicked.connect(self._export_csv)
        self._export_btn.setEnabled(False)
        self._parallel = QCheckBox("Paralelo")
        self._parallel.setToolTip("Procesa las curvas de cada mapa en varios procesos")
        self._status = QLabel("sin lote")
        self._status.setProperty("role", "muted")
        bar.addWidget(self._open_btn)
        bar.addWidget(self._export_btn)
        bar.addWidget(self._parallel)
        self._windows_btn = QPushButton("Ventanas automáticas…")
        self._windows_btn.clicked.connect(self._open_windows)
        bar.addWidget(self._windows_btn)
        self._adhesion_btn = QPushButton("Adhesión por curva…")
        self._adhesion_btn.clicked.connect(lambda: self.open_adhesion())
        bar.addWidget(self._adhesion_btn)
        bar.addStretch(1)
        bar.addWidget(self._status)
        lay.addLayout(bar)

        self._model = QStandardItemModel(0, len(_HEADERS), root)
        self._model.setHorizontalHeaderLabels(list(_HEADERS))
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._table, 1)
        self._on_batch_ready(self._vm.result)
        self._on_computing(self._vm.computing)
        return root

    # ---- acciones ----
    def open_adhesion(self, source: str | None = None) -> None:
        from spmkit.gui.widgets.adhesion_review import AdhesionDialog

        if not hasattr(self, "_adhesion_dialog"):
            self._adhesion_dialog = AdhesionDialog(self)
        dlg = self._adhesion_dialog
        if source and not dlg.task:
            path = Path(source)
            index = next((i for i, m in enumerate(dlg.maps) if m.path == path), None)
            if index is None:
                dlg.start([path])
            else:
                dlg.files.setCurrentIndex(index)
        dlg.exec()

    def _open_windows(self) -> None:
        from spmkit.gui.widgets.auto_windows import AutoWindowDialog

        if not hasattr(self, "_window_dialog"):
            self._window_dialog = AutoWindowDialog(self)
        self._window_dialog.exec()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de curvas")
        if folder:
            self._vm.run(folder, parallel=self._parallel.isChecked())

    def _export_csv(self) -> None:
        result = self._vm.result
        if self._vm.computing or result is None or not result.rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "batch.csv", "CSV (*.csv)")
        if path:
            out = Path(path)
            if not out.suffix:
                out = out.with_suffix(".csv")
            try:
                result.to_csv(out)
            except (OSError, ValueError, TypeError, CsvError) as exc:
                self._status.setText(f"No se pudo exportar el CSV: {exc}")
                return
            self._status.setText("CSV exportado")

    # ---- reacciones ----
    def _show_status(self, message: str) -> None:
        self._status.setText(message)

    def _on_batch_ready(self, result: ForceBatchResult | None) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._export_btn.setEnabled(bool(result and result.rows) and not self._vm.computing)
        if result is None:
            self._status.setText("Procesando…" if self._vm.computing else "Sin lote")
            return
        if not result.rows:
            self._status.setText("No hay archivos de curvas compatibles")
            return
        for row in result.rows:
            self._model.appendRow(_row_items(row))
        self._status.setText(
            f"{result.n_ok} archivos OK · {result.n_failed} con error · "
            f"{result.n_curves_ok}/{result.n_curves} curvas procesadas"
        )

    def _on_computing(self, computing: bool) -> None:
        self._open_btn.setEnabled(not computing)
        self._open_btn.setText("Procesando…" if computing else "Abrir carpeta…")
        self._parallel.setEnabled(not computing)
        self._windows_btn.setEnabled(not computing)
        self._adhesion_btn.setEnabled(not computing)
        self._export_btn.setEnabled(not computing and self._model.rowCount() > 0)
