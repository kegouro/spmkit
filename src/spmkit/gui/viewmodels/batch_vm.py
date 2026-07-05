"""ViewModel de procesamiento por lotes — corre una carpeta de curvas con la receta.

Reutiliza la receta del :class:`ForceViewModel` (la que edita el panel de pipeline),
de modo que el batch aplica exactamente el mismo ajuste que se ve en vivo. El cómputo
va en un :class:`Task` fuera del hilo de UI; ``run_now`` es sincrónico para tests.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.forcebatch import ForceBatchResult, process_force_folder
from spmkit.gui.runtime.tasks import Task, run_task
from spmkit.gui.viewmodels.force_vm import ForceViewModel


class BatchViewModel(QObject):
    """Estado observable del batch de una carpeta de curvas de fuerza."""

    batchReady = pyqtSignal(object)  # ForceBatchResult
    taskStarted = pyqtSignal(object)  # Task (el shell lo engancha a la barra)
    statusChanged = pyqtSignal(str)
    computingChanged = pyqtSignal(bool)

    def __init__(self, force_vm: ForceViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._force_vm = force_vm
        self._result: ForceBatchResult | None = None
        self._task: Task | None = None

    @property
    def result(self) -> ForceBatchResult | None:
        return self._result

    def run_now(self, folder: str | Path, parallel: bool = False) -> None:
        """Procesa la carpeta de forma sincrónica (tests / lotes chicos)."""
        self._result = process_force_folder(folder, self._force_vm.recipe, parallel=parallel)
        self.batchReady.emit(self._result)

    def run(self, folder: str | Path, parallel: bool = False) -> None:
        """Procesa la carpeta en un hilo worker; emite ``batchReady`` al terminar."""
        if self._task is not None:
            return
        task = Task(
            process_force_folder,
            folder,
            self._force_vm.recipe,
            parallel=parallel,
            provide_progress=True,
        )
        task.signals.done.connect(self._on_done)
        task.signals.error.connect(lambda exc: self.statusChanged.emit(f"batch falló: {exc}"))
        task.signals.finished.connect(self._on_finished)
        self._task = task
        self.computingChanged.emit(True)
        self.taskStarted.emit(task)
        run_task(task)

    def _on_done(self, result: object) -> None:
        self._result = result if isinstance(result, ForceBatchResult) else None
        self.batchReady.emit(self._result)

    def _on_finished(self) -> None:
        self._task = None
        self.computingChanged.emit(False)
