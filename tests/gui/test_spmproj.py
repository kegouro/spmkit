"""Test del proyecto .spmproj en Fathom: guardar y reabrir (archivo + params)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog

from spmkit.core.project import load_project
from spmkit.gui.app_workspace import _load_into, _open_project, _save_project, build_workspace

_SAMPLES = Path(__file__).resolve().parents[2] / "reference" / "samples"


def _force_sample() -> Path | None:
    if not _SAMPLES.exists():
        return None
    return next(iter(_SAMPLES.glob("*.jpk-force")), None)


def test_spmproj_save_incluye_hash_sin_cargar_datos(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    contenido = b"sesion-gui-spmkit"
    archivo = tmp_path / "sesion.bin"
    archivo.write_bytes(contenido)
    proj = tmp_path / "sesion.spmproj"
    ws = build_workspace()
    qtbot.addWidget(ws)
    vm = ws.panel("force_canvas")._vm
    session = {"path": str(archivo), "kind": "force"}
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(proj), ""))
    )

    _save_project(ws, vm, session)

    state = load_project(proj)
    assert state.files[0].sha256 == hashlib.sha256(contenido).hexdigest()


def test_spmproj_save_sin_origen_conserva_archivo_sin_hash(
    qtbot, tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    origen = tmp_path / "origen_ausente.jpk-force"
    proj = tmp_path / "sesion_sin_origen.spmproj"
    ws = build_workspace()
    qtbot.addWidget(ws)
    vm = ws.panel("force_canvas")._vm
    session = {"path": str(origen), "kind": "force"}
    statuses: list[str] = []
    monkeypatch.setattr(ws, "show_status", statuses.append)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(proj), ""))
    )

    _save_project(ws, vm, session)

    state = load_project(proj)
    assert state.files[0].path == str(origen)
    assert state.files[0].kind == "force"
    assert state.files[0].sha256 is None
    assert "sin hash" in statuses[-1].lower()


def test_spmproj_save_and_open(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sample = _force_sample()
    if sample is None:
        pytest.skip("sin sample .jpk-force (corre scripts/fetch_samples.py)")
    proj = tmp_path / "sesion.spmproj"
    ws = build_workspace()
    qtbot.addWidget(ws)
    vm = ws.panel("force_canvas")._vm
    img_vm = ws.panel("image_canvas")._vm
    session: dict = {}
    _load_into(ws, vm, img_vm, str(sample), session, kind_hint="force")
    assert vm.n_curves >= 1 and session["path"] == str(sample)

    vm.set_param("tip_radius", 2.5e-8)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(proj), ""))
    )
    _save_project(ws, vm, session)

    state = load_project(proj)  # el .spmproj quedó bien escrito
    assert state.files[0].path == str(sample) and state.files[0].kind == "force"
    assert abs(state.params["tip_radius"] - 2.5e-8) < 1e-12
    assert state.perspective == "force"

    vm.set_param("tip_radius", 1e-8)  # cambiar para verificar que se restaura
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(proj), ""))
    )
    _open_project(ws, vm, img_vm, session)
    assert abs(vm.params["tip_radius"] - 2.5e-8) < 1e-12  # params restaurados
    assert vm.n_curves >= 1  # archivo reabierto
