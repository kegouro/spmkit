"""Interactive per-curve decisions for single- and multi-file NID adhesion review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.adhesion_review import (
    AdhesionMap,
    export_review,
    export_traces,
    read_for_review,
    review_maps,
)
from spmkit.core.models import ForceVolume
from spmkit.gui.runtime.tasks import Task, run_task

_ROOT = QModelIndex()


class ReviewTable(QAbstractTableModel):
    headers = ("Incluir", "Curva [0…]", "Adhesión (nN)", "Recomendación")

    def __init__(self, data_map: AdhesionMap, parent: QWidget) -> None:
        super().__init__(parent)
        self.data_map = data_map

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.data_map.curves)

    def columnCount(self, parent: QModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if index.isValid() and index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        r = self.data_map.curves[index.row()]
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return Qt.CheckState.Checked if r.included else Qt.CheckState.Unchecked
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return (
                "",
                str(r.index),
                f"{r.adhesion_n*1e9:.5g}" if r.adhesion_n is not None else "—",
                r.warning,
            )[index.column()]
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.column() != 0 or role != Qt.ItemDataRole.CheckStateRole:
            return False
        self.data_map.curves[index.row()].included = Qt.CheckState(value) == Qt.CheckState.Checked
        self.dataChanged.emit(index, index, [role])
        return True


class AdhesionDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adhesión por curva · mapas NID")
        self.resize(990, 690)
        self.maps: list[AdhesionMap] = []
        self.volume: ForceVolume | None = None
        self.task: Task | None = None
        self.model: ReviewTable | None = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.open_btn = QPushButton("Elegir mapas NID…")
        self.open_btn.clicked.connect(self.choose)
        self.files = QComboBox()
        self.files.setAccessibleName("Mapa que revisar")
        self.files.currentIndexChanged.connect(self.select_map)
        top.addWidget(self.open_btn)
        top.addWidget(self.files, 1)
        self.cancel = QPushButton("Cancelar cálculo")
        self.cancel.clicked.connect(self.cancel_task)
        top.addWidget(self.cancel)
        layout.addLayout(top)
        self.message = QLabel("Selecciona uno o varios mapas. Todas las curvas empiezan incluidas.")
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        self.message.setToolTip(
            "Adhesión = referencia de cola menos mínimo de retracción. "
            "La referencia es la mediana del último 10 %, con al menos 5 muestras."
        )
        layout.addWidget(self.message)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        layout.addWidget(self.progress)
        plots = QHBoxLayout()
        self.grid = pg.PlotWidget()
        self.grid.setLabel("bottom", "Columna inferida")
        self.grid.setLabel("left", "Fila inferida")
        self.image = pg.ImageItem(axisOrder="row-major")
        self.image.setColorMap(pg.colormap.get("viridis"))
        self.grid.addItem(self.image)
        self.cell = self.grid.plot(
            [], [], pen=None, symbol="s", symbolSize=12, symbolBrush=None, symbolPen="r"
        )
        self.grid.scene().sigMouseClicked.connect(self.pick_cell)
        self.chart = pg.PlotWidget()
        self.chart.setLabel("left", "Fuerza", units="nN")
        self.chart.getAxis("left").enableAutoSIPrefix(False)
        self.chart.getAxis("bottom").enableAutoSIPrefix(False)
        self.chart.addLegend()
        self.approach = self.chart.plot(name="Aproximación", pen=pg.mkPen("#2586ad", width=2))
        self.retract = self.chart.plot(name="Retracción", pen=pg.mkPen("#cb7936", width=2))
        self.minimum = self.chart.plot(
            [], [], pen=None, symbol="o", symbolSize=9, symbolBrush="#bb4153"
        )
        self.baseline = pg.InfiniteLine(
            angle=0, pen=pg.mkPen("#808080", style=Qt.PenStyle.DashLine)
        )
        self.chart.addItem(self.baseline)
        self.baseline.hide()
        plots.addWidget(self.grid, 1)
        plots.addWidget(self.chart, 2)
        layout.addLayout(plots, 2)
        self.axis = QComboBox()
        self.axis.addItems(["Separación si está disponible", "Altura del sensor"])
        self.axis.currentIndexChanged.connect(self.draw_curve)
        self.axis.setAccessibleName("Coordenada horizontal")
        layout.addWidget(self.axis)
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 2)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        self.next_warning = QPushButton("Revisar siguiente aviso…")
        self.next_warning.clicked.connect(self.review_warning)
        self.export_rows = QPushButton("Exportar curvas…")
        self.export_rows.clicked.connect(lambda: self.export(False))
        self.export_summary = QPushButton("Exportar resumen…")
        self.export_summary.clicked.connect(lambda: self.export(True))
        self.samples = QPushButton("Exportar trazas completas…")
        self.samples.clicked.connect(self.save_traces)
        for button in (self.next_warning, self.export_rows, self.export_summary, self.samples):
            actions.addWidget(button)
        self.figures = QPushButton("Figuras…")
        menu = QMenu(self.figures)
        menu.addAction("Adhesión de las curvas incluidas…", self.export_figures)
        menu.addAction("Ventanas automáticas de las curvas incluidas…", self.selected_windows)
        self.figures.setMenu(menu)
        actions.addWidget(self.figures)
        layout.addLayout(actions)
        self.busy(False)

    def choose(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar mapas con curvas de fuerza", "", "NanoSurf (*.nid *.NID)"
        )
        if paths:
            self.start([Path(p) for p in paths])

    def start(self, paths: list[Path]) -> None:
        if self.task or not paths:
            return
        if any(not r.included for m in self.maps for r in m.curves) and (
            QMessageBox.question(
                self,
                "Nueva revisión",
                "¿Sustituir esta selección por otro lote?",
                defaultButton=QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.progress.setValue(0)
        self.launch(Task(review_maps, paths, provide_progress=True), self.loaded)

    def launch(self, task: Task, on_done: Any) -> None:
        self.task = task
        self.busy(True)
        task.signals.done.connect(on_done)
        task.signals.progress.connect(self.on_progress)
        task.signals.cancelled.connect(lambda: self.message.setText("Operación cancelada"))
        task.signals.error.connect(lambda e: self.message.setText(str(e)))
        task.signals.finished.connect(self.finished)
        run_task(task)

    def finished(self) -> None:
        self.task = None
        self.busy(False)

    def busy(self, on: bool) -> None:
        self.open_btn.setEnabled(not on)
        self.files.setEnabled(not on)
        self.table.setEnabled(not on)
        self.cancel.setEnabled(on)
        self.progress.setVisible(on)
        for b in (self.export_rows, self.export_summary, self.samples):
            b.setEnabled(bool(self.maps) and not on)
        self.figures.setEnabled(not on and any(r.included for m in self.maps for r in m.curves))
        self.next_warning.setEnabled(
            not on
            and self.model is not None
            and any(r.warning and r.included for r in self.model.data_map.curves)
        )

    def cancel_task(self) -> None:
        if self.task:
            self.task.cancel()

    def reject(self) -> None:
        self.cancel_task()
        super().reject()

    def on_progress(self, fraction: float, msg: str) -> None:
        self.progress.setValue(round(fraction * 1000))
        self.message.setText(msg)

    def loaded(self, result: tuple[list[AdhesionMap], ForceVolume | None]) -> None:
        self.maps, self.volume = result
        self.files.blockSignals(True)
        self.files.clear()
        for m in self.maps:
            self.files.addItem(m.path.name)
            self.files.setItemData(self.files.count() - 1, str(m.path), Qt.ItemDataRole.ToolTipRole)
        initial = next((i for i, m in enumerate(self.maps) if not m.error), 0)
        self.files.setCurrentIndex(initial)
        self.files.blockSignals(False)
        self.show_map(initial)
        count = sum(len(m.curves) for m in self.maps)
        flagged = sum(bool(r.warning) for m in self.maps for r in m.curves)
        failed = sum(bool(m.error) for m in self.maps)
        self.message.setText(
            f"Lote: {count} curvas · {flagged} con aviso · {failed} archivos con error. "
            + (self.maps[initial].error or "Todas las curvas empiezan incluidas.")
        )

    def select_map(self, index: int) -> None:
        if index < 0 or self.task is not None:
            return
        self.volume = None
        self.show_map(index)
        m = self.maps[index]
        if m.error:
            self.message.setText(m.error)
            return
        self.message.setText("Leyendo las trazas completas…")
        self.launch(Task(read_for_review, m.path, m.digest), self.traces_loaded)
        self.cancel.setEnabled(False)  # a single file read completes as one operation

    def traces_loaded(self, result: tuple[str, ForceVolume]) -> None:
        _, self.volume = result
        self.message.setText("Mapa cargado")
        self.draw_curve()

    def show_map(self, index: int) -> None:
        if self.model is not None:
            self.model.deleteLater()
        self.model = ReviewTable(self.maps[index], self)
        self.table.setModel(self.model)
        self.table.selectionModel().currentRowChanged.connect(self.draw_curve)
        self.model.dataChanged.connect(self.refresh_selection)
        self.table.selectRow(0)
        self.refresh_selection()
        self.draw_curve()
        self.grid.autoRange()

    def refresh_selection(self) -> None:
        if self.model is None:
            return
        m = self.model.data_map
        self.figures.setEnabled(
            self.task is None and any(r.included for m in self.maps for r in m.curves)
        )
        vals = m.selected_values()
        flags = sum(bool(r.warning) for r in m.curves)
        median = f"{np.median(vals)*1e9:.4g} nN" if vals else "—"
        self.summary.setText(
            f"{sum(r.included for r in m.curves)}/{len(m.curves)} incluidas · "
            f"{len(vals)} con adhesión · Mediana {median} · {flags} con aviso"
        )
        self.next_warning.setEnabled(any(r.warning and r.included for r in m.curves))
        if m.curves:
            array = np.array(
                [
                    r.adhesion_n * 1e9 if r.included and r.adhesion_n is not None else np.nan
                    for r in m.curves
                ]
            ).reshape(m.shape)
            lo, hi = (min(vals) * 1e9, max(vals) * 1e9) if vals else (0.0, 1.0)
            self.image.setImage(array, autoLevels=False, levels=(lo, hi if hi > lo else lo + 1))
            self.grid.setTitle(
                f"Adhesión · {lo:.3g} a {hi:.3g} nN" if vals else "Sin valores seleccionados"
            )
        else:
            self.image.clear()
            self.grid.setTitle("Sin curvas")

    def draw_curve(self) -> None:
        self.approach.clear()
        self.retract.clear()
        self.minimum.clear()
        self.baseline.hide()
        self.cell.clear()
        i = self.table.currentIndex().row()
        if self.model is None or i < 0:
            return
        m = self.model.data_map
        y, x = divmod(i, m.shape[1])
        self.cell.setData([x + 0.5], [y + 0.5])
        if self.volume is None:
            return
        try:
            c = self.volume.curve(i)
        except (ValueError, ArithmeticError) as exc:
            self.message.setText(str(exc))
            return
        r = m.curves[i]
        branches = [(c.extend, self.approach), (c.retract, self.retract)]
        has_sep = any(s is not None and s.separation is not None for s, _ in branches)
        sep = self.axis.currentIndex() == 0 and has_sep
        self.chart.setLabel("bottom", "Separación" if sep else "Altura del sensor", units="nm")
        missing = []
        unverified = False
        for s, line in branches:
            if s is None or s.force is None:
                continue
            coord = s.separation if sep else s.raw_height
            if coord is None:
                missing.append("aproximación" if s is c.extend else "retracción")
                continue
            unverified |= sep and s.metadata.get("separation_status") == "unverified"
            line.setData(coord * 1e9, s.force * 1e9)
            if s is c.retract and r.minimum_index is not None and r.baseline_n is not None:
                j = r.minimum_index
                self.minimum.setData([coord[j] * 1e9], [s.force[j] * 1e9])
                self.baseline.setPos(r.baseline_n * 1e9)
                self.baseline.show()
        notes = ["Separación del instrumento sin contraste"] if unverified else []
        if missing:
            notes.append("Sin separación en " + ", ".join(missing) + " · ver Altura del sensor")
        self.chart.setTitle(" · ".join(notes))
        self.chart.autoRange()

    def pick_cell(self, event: Any) -> None:
        if (
            self.model is None
            or self.task is not None
            or event.button() != Qt.MouseButton.LeftButton
        ):
            return
        point = self.image.mapFromScene(event.scenePos())
        m = self.model.data_map
        if 0 <= point.x() < m.shape[1] and 0 <= point.y() < m.shape[0]:
            self.table.selectRow(int(point.y()) * m.shape[1] + int(point.x()))

    def review_warning(self) -> None:
        if self.model is None:
            return
        rows = self.model.data_map.curves
        current = self.table.currentIndex().row()
        flagged = [r for r in rows if r.warning and r.included]
        if not flagged:
            return
        r = next((r for r in flagged if r.index > current), flagged[0])
        self.table.selectRow(r.index)
        answer = QMessageBox.question(
            self,
            "Revisar adhesión",
            f"Curva {r.index} · {r.warning}.\n¿Excluirla del resumen de este mapa?",
            defaultButton=QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.model.setData(
                self.model.index(r.index, 0),
                Qt.CheckState.Unchecked,
                Qt.ItemDataRole.CheckStateRole,
            )

    def export(self, summary: bool) -> None:
        name = "adhesion_resumen.csv" if summary else "adhesion_curvas.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar revisión de adhesión", name, "CSV (*.csv)"
        )
        if path:
            out = Path(path)
            try:
                export_review(
                    self.maps, out if out.suffix else out.with_suffix(".csv"), summary=summary
                )
                self.message.setText("CSV guardado")
            except (ValueError, OSError) as exc:
                self.message.setText(str(exc))

    def save_traces(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar curvas seleccionadas", "trazas.csv", "CSV (*.csv)"
        )
        if path:
            out = Path(path)
            self.launch(
                Task(
                    export_traces,
                    self.maps,
                    out if out.suffix else out.with_suffix(".csv"),
                    provide_progress=True,
                ),
                lambda _: self.message.setText("Trazas completas guardadas"),
            )

    def selected_windows(self) -> None:
        from spmkit.gui.widgets.auto_windows import AutoWindowDialog

        dialog = AutoWindowDialog(self, reviewed=self.maps)
        dialog.exec()
        dialog.deleteLater()

    def export_figures(self) -> None:
        from spmkit.core.viz.window_figures import export_batch_figures

        folder = QFileDialog.getExistingDirectory(self, "Crear carpeta de figuras de adhesión en…")
        if folder:
            self.launch(
                Task(export_batch_figures, self.maps, Path(folder), provide_progress=True),
                lambda path: self.message.setText(f"Figuras guardadas en {path}"),
            )
