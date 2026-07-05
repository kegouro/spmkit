"""Runtime de la GUI: ejecución fuera del hilo de UI, estado y persistencia."""

from spmkit.gui.runtime.tasks import Task, TaskCancelled, TaskSignals, run_task

__all__ = ["Task", "TaskSignals", "TaskCancelled", "run_task"]
