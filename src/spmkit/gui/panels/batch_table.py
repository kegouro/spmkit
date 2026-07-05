"""Tabla de procesamiento por lotes — reemplaza el batch de ANA/JPK.

Corre la receta activa sobre una carpeta de curvas (``.jpk-force``/``.nid``) y muestra
una fila por archivo con módulo, adhesión y disipación medianos. Exporta a CSV. El
cómputo pesado va fuera del hilo de UI (barra de progreso cancelable en el shell).
"""

from __future__ import annotations

import math

from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
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
    "OK",
    "E med (kPa)",
    "E σ (kPa)",
    "Adh (nN)",
    "Disip (fJ)",
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
        self._status = QLabel("sin lote")
        self._status.setProperty("role", "muted")
        bar.addWidget(self._open_btn)
        bar.addWidget(self._export_btn)
        bar.addStretch(1)
        bar.addWidget(self._status)
        lay.addLayout(bar)

        self._model = QStandardItemModel(0, len(_HEADERS))
        self._model.setHorizontalHeaderLabels(list(_HEADERS))
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._table, 1)
        return root

    # ---- acciones ----
    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de curvas")
        if folder:
            self._status.setText("procesando…")
            self._vm.run(folder)

    def _export_csv(self) -> None:
        result = self._vm.result
        if result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "batch.csv", "CSV (*.csv)")
        if path:
            result.to_csv(path)
            self._status.setText("CSV exportado")

    # ---- reacciones ----
    def _on_batch_ready(self, result: ForceBatchResult | None) -> None:
        self._model.removeRows(0, self._model.rowCount())
        if result is None:
            self._status.setText("sin lote")
            return
        for row in result.rows:
            self._model.appendRow(_row_items(row))
        self._export_btn.setEnabled(bool(result.rows))
        self._status.setText(f"{result.n_ok} ok · {result.n_failed} con error")

    def _on_computing(self, computing: bool) -> None:
        self._open_btn.setEnabled(not computing)
        self._open_btn.setText("Procesando…" if computing else "Abrir carpeta…")
