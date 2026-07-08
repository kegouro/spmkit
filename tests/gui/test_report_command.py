"""Test del comando 'Generar informe' de Fathom (genera HTML sin bloquear la UI)."""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog

from spmkit.gui.app_workspace import _generate_report, build_workspace


def test_report_generates(qtbot, tmp_path, synthetic_volume, monkeypatch) -> None:  # type: ignore[no-untyped-def]  # noqa: E501
    out = tmp_path / "informe.html"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), ""))
    )
    ws = build_workspace()
    qtbot.addWidget(ws)
    assert any("informe" in c.title.lower() for c in ws._commands)  # comando presente

    vm = ws.panel("force_canvas")._vm
    vm.set_volume(synthetic_volume(6))
    _generate_report(ws, vm)  # lanza el informe en un hilo (.html → sólo HTML)

    def _report_written() -> bool:
        # esperar el CONTENIDO, no solo que el archivo exista: el hilo lo crea vacío y
        # luego escribe, así que ``out.exists`` puede dispararse antes del flush (flaky).
        try:
            return "espectroscopía de fuerza" in out.read_text(encoding="utf-8")
        except OSError:
            return False

    qtbot.waitUntil(_report_written, timeout=15000)
    assert "espectroscopía de fuerza" in out.read_text(encoding="utf-8")
