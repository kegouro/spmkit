"""Tests de la extensibilidad por módulos (F4): añadir un módulo debe ser un trámite tonto."""

from __future__ import annotations

from spmkit.gui.builtin_modules import BUILTIN_MODULES
from spmkit.gui.extensions import (
    ModuleContext,
    ModuleSpec,
    PanelSpec,
    PerspectiveSpec,
    assemble,
    discovered_modules,
    spec_metadata,
)
from spmkit.gui.panels.base import Panel
from spmkit.gui.shell.workspace import Workspace

_ALL_PERSPECTIVES = {
    "image",
    "grains",
    "spectral",
    "resonance",
    "force",
    "smfs",
    "map",
    "batch",
    "figure",
    "view3d",
    "simulator",
}


def _ctx() -> ModuleContext:
    return ModuleContext(force_vm=None, image_vm=None, map_vm=None, batch_vm=None)


def test_builtin_modules_expose_all_perspectives() -> None:
    perspectives, labels, areas, central = spec_metadata(BUILTIN_MODULES)
    assert {p.key for p in perspectives} == _ALL_PERSPECTIVES
    assert "image_canvas" in central and "navigator" not in central  # central vs dock
    assert areas["navigator"] == "left" and areas["pipeline"] == "bottom"
    assert labels["grains_canvas"] == "Granos"


def test_discovered_modules_is_tolerant() -> None:
    # Sin entry-points instalados → lista vacía; nunca lanza.
    assert isinstance(discovered_modules(), list)


def test_adding_a_module_is_one_spec(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Un módulo nuevo = un ModuleSpec; aparece en el layout sin tocar la shell."""
    built: list[object] = []

    def factory(ctx: ModuleContext) -> Panel:
        built.append(ctx)
        return Panel()

    demo = ModuleSpec(
        name="demo",
        panels=(PanelSpec("demo_canvas", "Demo", factory, area="central"),),
        perspectives=(PerspectiveSpec("demo", "Demo", ("demo_canvas",)),),
    )
    layout = assemble([demo], _ctx())
    assert built  # la factory se invocó
    assert "demo_canvas" in layout.panels and "demo_canvas" in layout.central_panels
    assert any(p.key == "demo" for p in layout.perspectives)

    # La shell lo arma y lo activa tal cual, sin cambios en workspace.py.
    ws = Workspace(
        panels=layout.panels,
        perspectives=layout.perspectives,
        panel_labels=layout.panel_labels,
        dock_areas=layout.dock_areas,
        central_panels=layout.central_panels,
    )
    qtbot.addWidget(ws)
    ws.set_perspective("demo")
    assert ws.active_perspective == "demo"


def test_first_module_wins_on_key_clash() -> None:
    def f1(ctx: ModuleContext) -> Panel:
        return Panel()

    def f2(ctx: ModuleContext) -> Panel:
        return Panel()

    a = ModuleSpec("a", panels=(PanelSpec("shared", "A", f1),))
    b = ModuleSpec("b", panels=(PanelSpec("shared", "B", f2),))
    _, labels, _, _ = spec_metadata([a, b])
    assert labels["shared"] == "A"  # gana el primero (fábrica antes que plugin)
