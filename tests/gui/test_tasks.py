"""Tests del runtime de tareas (QThreadPool + progreso cancelable)."""

from __future__ import annotations

import threading
import time

from spmkit.gui.runtime.tasks import Task, run_task


def test_task_runs_and_returns(qtbot) -> None:  # type: ignore[no-untyped-def]
    task = Task(lambda: 6 * 7)
    with qtbot.waitSignal(task.signals.done, timeout=3000) as blocker:
        run_task(task)
    assert blocker.args == [42]


def test_task_emits_progress(qtbot) -> None:  # type: ignore[no-untyped-def]
    def work(progress):  # type: ignore[no-untyped-def]
        for i in range(3):
            progress((i + 1) / 3, f"paso {i}")
        return "ok"

    task = Task(work, provide_progress=True)
    records: list[float] = []
    task.signals.progress.connect(lambda f, m: records.append(f))
    with qtbot.waitSignal(task.signals.done, timeout=3000):
        run_task(task)
    assert len(records) == 3
    assert records[-1] == 1.0


def test_task_reports_error(qtbot) -> None:  # type: ignore[no-untyped-def]
    def boom():  # type: ignore[no-untyped-def]
        raise ValueError("nope")

    task = Task(boom)
    with qtbot.waitSignal(task.signals.error, timeout=3000) as blocker:
        run_task(task)
    assert isinstance(blocker.args[0], ValueError)


def test_task_can_be_cancelled(qtbot) -> None:  # type: ignore[no-untyped-def]
    started = threading.Event()

    def work(progress):  # type: ignore[no-untyped-def]
        started.set()
        for i in range(300):
            progress(i / 300, "")
            time.sleep(0.01)
        return "done"

    task = Task(work, provide_progress=True)
    with qtbot.waitSignal(task.signals.cancelled, timeout=5000):
        run_task(task)
        started.wait(2.0)
        task.cancel()
