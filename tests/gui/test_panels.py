"""Tests del Panel base y su sandbox de errores."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from spmkit.gui.panels.base import Panel


def test_panel_builds_ok(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = Panel()
    qtbot.addWidget(panel)
    assert not panel.errored


def test_panel_sandbox_catches_build_error(qtbot) -> None:  # type: ignore[no-untyped-def]
    class Broken(Panel):
        title = "Roto"

        def build(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom en build")

    panel = Broken()
    qtbot.addWidget(panel)
    assert panel.errored  # muestra Error Card, no tumba la app


def test_panel_rebuild_recovers(qtbot) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    class Flaky(Panel):
        def build(self):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("primer intento falla")
            return QLabel("ok")

    panel = Flaky()
    qtbot.addWidget(panel)
    assert panel.errored
    panel.rebuild()
    assert not panel.errored


def test_panel_refresh_safe_isolates(qtbot) -> None:  # type: ignore[no-untyped-def]
    class RefreshBoom(Panel):
        def refresh(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom en refresh")

    panel = RefreshBoom()
    qtbot.addWidget(panel)
    assert not panel.errored  # build ok
    panel.refresh_safe()
    assert panel.errored  # refresh fallido → Error Card
