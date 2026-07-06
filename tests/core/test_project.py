"""Tests del proyecto .spmproj (save/load, versionado, tolerancia)."""

from __future__ import annotations

import json

from spmkit.core.project import OpenFile, ProjectState, load_project, save_project


def test_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state = ProjectState(
        files=[OpenFile("a.nid", "force"), OpenFile("b.gwy", "image")],
        params={"model": "sphere", "tip_radius": 1e-8},
        perspective="map",
    )
    path = save_project(state, tmp_path / "sesion.spmproj")
    loaded = load_project(path)
    assert [f.path for f in loaded.files] == ["a.nid", "b.gwy"]
    assert [f.kind for f in loaded.files] == ["force", "image"]
    assert loaded.params["model"] == "sphere"
    assert loaded.perspective == "map"
    assert loaded.version == 1


def test_tolerant_to_missing_and_unknown_fields(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # .spmproj "viejo"/parcial: sin params ni perspective, con un campo extra.
    path = tmp_path / "viejo.spmproj"
    path.write_text(json.dumps({"files": [{"path": "x.nid"}], "futuro": 42}), encoding="utf-8")
    state = load_project(path)
    assert state.files[0].path == "x.nid"
    assert state.files[0].kind == "force"  # default
    assert state.params == {} and state.perspective == "force"


def test_ignores_malformed_file_entries(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "malo.spmproj"
    path.write_text(json.dumps({"files": [{"path": "ok.nid"}, {}, "basura", {"kind": "x"}]}))
    state = load_project(path)
    assert [f.path for f in state.files] == ["ok.nid"]  # solo el válido
