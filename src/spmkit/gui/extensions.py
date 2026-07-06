"""Extensibilidad de Fathom — **módulos de workspace**.

Un :class:`ModuleSpec` empaqueta lo que aporta una función/dominio: sus **paneles**
(con una *factory* perezosa) y sus **perspectivas**. ``build_workspace`` deriva de la
lista de módulos TODO lo demás (barra de perspectivas, docks, lienzos centrales, comandos):
**añadir un módulo es añadir un ``ModuleSpec``** (o publicarlo por entry-point) — nada de
tocar la shell. Es la base para que ``spmkit`` sea un *host* multi-física y Fathom una de
sus extensiones (AFM/fuerza); otros cores registran sus propios módulos por el mismo canal.

Esta capa es deliberadamente ligera (sólo ``dataclasses``/``typing``): las *factories*
importan sus paneles/ViewModels al construirse, no al importar el módulo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - sólo para anotaciones
    from spmkit.gui.panels.base import Panel
    from spmkit.gui.shell.workspace import Workspace

#: Grupo de entry-points para módulos de terceros / otros cores multi-física.
ENTRY_POINT_GROUP = "spmkit.gui.modules"

#: Áreas de acoplado válidas para un panel (la shell las traduce a Qt).
Area = str  # "central" | "left" | "right" | "bottom" | "top"


@dataclass(frozen=True)
class PanelSpec:
    """Un panel que aporta un módulo: clave, etiqueta, dónde va y cómo se construye."""

    key: str
    label: str
    factory: Callable[[ModuleContext], Panel]  # (contexto) → Panel
    area: Area = "central"


@dataclass(frozen=True)
class PerspectiveSpec:
    """Una perspectiva (preset de layout): qué paneles muestra, por clave."""

    key: str
    label: str
    panels: tuple[str, ...]


@dataclass(frozen=True)
class ModuleSpec:
    """Todo lo que aporta un módulo de workspace."""

    name: str
    panels: tuple[PanelSpec, ...] = ()
    perspectives: tuple[PerspectiveSpec, ...] = ()
    #: Gancho opcional tras construir la ventana ``(workspace, contexto)``: conecta señales
    #: del módulo a la shell (estado/progreso) y registra sus comandos.
    wire: Callable[[Workspace, ModuleContext], None] | None = None


@dataclass
class ModuleContext:
    """Estado compartido que las *factories* de los módulos cablean a sus paneles.

    Los *hubs* de ViewModel se crean una vez (en ``build_workspace``) y se comparten: un
    solo archivo abierto alimenta imagen, granos, espectral, figura, 3D (``image_vm``) o
    curva, mapa y batch (``force_vm``). ``store`` deja a un módulo guardar sus propios VMs.
    """

    force_vm: Any
    image_vm: Any
    map_vm: Any
    batch_vm: Any
    session: dict[str, Any] = field(default_factory=dict)
    store: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Assembly:
    """Resultado de ensamblar los módulos: lo que la shell necesita para armarse."""

    panels: dict[str, Panel]
    perspectives: tuple[PerspectiveSpec, ...]
    panel_labels: dict[str, str]
    dock_areas: dict[str, Area]  # sólo paneles no-centrales
    central_panels: frozenset[str]


def discovered_modules() -> list[ModuleSpec]:
    """Módulos publicados por entry-point (terceros / otros cores). Tolerante a fallos."""
    mods: list[ModuleSpec] = []
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - API vieja de importlib.metadata
        eps = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
    for ep in eps:
        try:
            obj = ep.load()
            spec = obj() if callable(obj) and not isinstance(obj, ModuleSpec) else obj
            if isinstance(spec, ModuleSpec):
                mods.append(spec)
        except Exception:  # noqa: BLE001 - un plugin roto no debe tumbar la app
            continue
    return mods


def iter_modules() -> list[ModuleSpec]:
    """Todos los módulos: los de fábrica (Fathom) + los descubiertos por entry-point."""
    from spmkit.gui.builtin_modules import BUILTIN_MODULES

    return [*BUILTIN_MODULES, *discovered_modules()]


def spec_metadata(
    modules: tuple[ModuleSpec, ...] | list[ModuleSpec],
) -> tuple[tuple[PerspectiveSpec, ...], dict[str, str], dict[str, Area], frozenset[str]]:
    """Metadatos de los módulos **sin construir paneles**: perspectivas, etiquetas, áreas,
    y el conjunto de paneles centrales. Clave repetida: gana la primera (fábrica > plugin).
    """
    labels: dict[str, str] = {}
    areas: dict[str, Area] = {}
    central: set[str] = set()
    perspectives: list[PerspectiveSpec] = []
    for module in modules:
        for spec in module.panels:
            if spec.key in labels:
                continue
            labels[spec.key] = spec.label
            if spec.area == "central":
                central.add(spec.key)
            else:
                areas[spec.key] = spec.area
        perspectives.extend(module.perspectives)
    return tuple(perspectives), labels, areas, frozenset(central)


def assemble(modules: list[ModuleSpec], ctx: ModuleContext) -> Assembly:
    """Construye los paneles y agrega perspectivas/etiquetas/áreas de una lista de módulos.

    Una clave de panel repetida entre módulos: gana la primera (los de fábrica antes que
    los descubiertos), así un plugin no puede pisar un panel de Fathom por accidente.
    """
    perspectives, labels, areas, central = spec_metadata(modules)
    panels: dict[str, Panel] = {}
    for module in modules:
        for spec in module.panels:
            if spec.key not in panels:
                panels[spec.key] = spec.factory(ctx)
    return Assembly(
        panels=panels,
        perspectives=perspectives,
        panel_labels=labels,
        dock_areas=areas,
        central_panels=central,
    )
