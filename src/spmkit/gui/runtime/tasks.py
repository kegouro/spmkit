"""Ejecución fuera del hilo de UI — contrato: nada pesado bloquea la interfaz.

Toda operación costosa (ajustes, mapas de force-volume, reportes, cargas grandes) se
envuelve en un :class:`Task` (un ``QRunnable``) que corre en un ``QThreadPool``. El
progreso viaja por un ``pyqtSignal`` (que Qt encola de forma segura al hilo principal)
y la tarea es **cancelable**.

Fronteras de proceso (importante): si la función usa ``ProcessPoolExecutor`` (mapas),
los procesos hijo son cómputo puro y **jamás** tocan Qt; el pool corre dentro de este
hilo worker y el callback de progreso emite la señal desde aquí — nunca desde un hijo.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot


class TaskCancelled(Exception):
    """Se lanza dentro de la tarea cuando el usuario cancela."""


class TaskSignals(QObject):
    """Señales de una tarea (viven en un QObject para poder emitirse cross-thread)."""

    progress = pyqtSignal(float, str)  # fracción [0, 1], mensaje
    done = pyqtSignal(object)  # resultado
    error = pyqtSignal(Exception)  # excepción (nunca se traga en silencio)
    cancelled = pyqtSignal()
    finished = pyqtSignal()  # siempre, al final (éxito, error o cancelación)


class Task(QRunnable):
    """Envuelve ``fn(*args, **kwargs)`` para correrla en un ``QThreadPool``.

    Si ``provide_progress`` es ``True``, inyecta un callable ``progress(fracción, msg)``
    como kwarg ``progress`` de ``fn``; ese callable emite la señal y, si la tarea fue
    cancelada, lanza :class:`TaskCancelled` para abortar de forma limpia.
    """

    def __init__(
        self, fn: Callable[..., Any], *args: Any, provide_progress: bool = False, **kwargs: Any
    ) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False
        self.signals = TaskSignals()
        if provide_progress:
            self._kwargs["progress"] = self._on_progress

    def cancel(self) -> None:
        """Solicita la cancelación; surte efecto en el próximo reporte de progreso."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def _on_progress(self, fraction: float, message: str = "") -> None:
        if self._cancelled:
            raise TaskCancelled()
        self.signals.progress.emit(float(fraction), str(message))

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except TaskCancelled:
            self.signals.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 - se reporta, nunca se traga
            self.signals.error.emit(exc)
        else:
            self.signals.done.emit(result)
        finally:
            self.signals.finished.emit()


def run_task(task: Task, pool: QThreadPool | None = None) -> None:
    """Lanza ``task`` en ``pool`` (o el ``QThreadPool`` global)."""
    (pool or QThreadPool.globalInstance()).start(task)
