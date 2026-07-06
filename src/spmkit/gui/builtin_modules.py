"""Módulos de fábrica de Fathom — la extensión AFM/fuerza del *host* ``spmkit``.

Cada módulo declara sus paneles (con *factory* perezosa) y perspectivas; ``build_workspace``
deriva de aquí la barra de perspectivas, los docks y los lienzos. **Añadir un módulo de
Fathom = añadir un ``ModuleSpec`` a :data:`BUILTIN_MODULES`.** Un módulo de terceros u otro
core multi-física se publica por entry-point (grupo ``spmkit.gui.modules``) sin tocar esto.

Las *factories* importan sus paneles/ViewModels al construirse (no al importar el módulo),
así este archivo es ligero. Los VMs propios de un módulo se guardan en ``ctx.store`` para
que su gancho ``wire`` los conecte a la shell.
"""

from __future__ import annotations

from spmkit.gui.extensions import ModuleContext, ModuleSpec, PanelSpec, PerspectiveSpec

# --------------------------------------------------------------------- factories


def _navigator(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.navigator import NavigatorPanel

    return NavigatorPanel(ctx.force_vm)


def _inspector(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.inspector import InspectorPanel

    return InspectorPanel(ctx.force_vm)


def _log(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.log_panel import LogPanel

    return LogPanel((ctx.force_vm, ctx.map_vm, ctx.batch_vm))


def _force_canvas(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.force_canvas import ForceCanvasPanel

    panel = ForceCanvasPanel(ctx.force_vm)
    ctx.store["force_canvas"] = panel  # build_workspace registra comandos pin/clear
    return panel


def _pipeline(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.pipeline_panel import PipelinePanel

    return PipelinePanel(ctx.force_vm)


def _map_canvas(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.map_canvas import MapCanvasPanel

    return MapCanvasPanel(ctx.map_vm, ctx.force_vm)


def _histogram(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.histogram_panel import HistogramPanel

    return HistogramPanel(ctx.map_vm)


def _batch_table(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.batch_table import BatchTablePanel

    return BatchTablePanel(ctx.batch_vm)


def _image_canvas(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.image_canvas import ImageCanvasPanel

    return ImageCanvasPanel(ctx.image_vm)


def _image_analysis(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.image_analysis import ImageAnalysisPanel

    return ImageAnalysisPanel(ctx.image_vm)


def _grains(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.grains_canvas import GrainsCanvasPanel
    from spmkit.gui.viewmodels import GrainsViewModel

    vm = GrainsViewModel(ctx.image_vm)
    ctx.store["grains_vm"] = vm
    return GrainsCanvasPanel(vm)


def _spectral(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.spectral_canvas import SpectralCanvasPanel
    from spmkit.gui.viewmodels import SpectralViewModel

    vm = SpectralViewModel(ctx.image_vm)
    ctx.store["spectral_vm"] = vm
    return SpectralCanvasPanel(vm)


def _figure(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.figure_panel import FigurePanel
    from spmkit.gui.viewmodels import FigureViewModel

    return FigurePanel(FigureViewModel(ctx.image_vm))


def _view3d(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.view3d_panel import View3DPanel
    from spmkit.gui.viewmodels import View3DViewModel

    return View3DPanel(View3DViewModel(ctx.image_vm))


def _simulator(ctx: ModuleContext):  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.simulator_panel import SimulatorPanel
    from spmkit.gui.viewmodels import SimulatorViewModel

    return SimulatorPanel(SimulatorViewModel())


# ------------------------------------------------------------------------- wiring


def _wire_force(ws, ctx: ModuleContext) -> None:  # type: ignore[no-untyped-def]
    ctx.map_vm.taskStarted.connect(ws.bind_task)
    ctx.batch_vm.taskStarted.connect(ws.bind_task)


def _wire_image(ws, ctx: ModuleContext) -> None:  # type: ignore[no-untyped-def]
    ctx.store["grains_vm"].statusChanged.connect(ws.show_status)
    ctx.store["spectral_vm"].statusChanged.connect(ws.show_status)


# ------------------------------------------------------------------------ módulos

#: Panel del árbol de datos, compartido por casi todas las perspectivas (shell).
_CORE = ModuleSpec(
    name="core",
    panels=(
        PanelSpec("navigator", "Datos", _navigator, area="left"),
        PanelSpec("inspector", "Inspector", _inspector, area="right"),
        PanelSpec("log", "Log", _log, area="bottom"),
    ),
)

_IMAGE = ModuleSpec(
    name="image",
    panels=(
        PanelSpec("image_canvas", "Imagen", _image_canvas),
        PanelSpec("image_analysis", "Análisis", _image_analysis, area="right"),
        PanelSpec("grains_canvas", "Granos", _grains),
        PanelSpec("spectral_canvas", "Espectral", _spectral),
    ),
    perspectives=(
        PerspectiveSpec("image", "Imagen", ("navigator", "image_canvas", "image_analysis")),
        PerspectiveSpec("grains", "Granos", ("navigator", "grains_canvas")),
        PerspectiveSpec("spectral", "Espectral", ("navigator", "spectral_canvas")),
    ),
    wire=_wire_image,
)

_FORCE = ModuleSpec(
    name="force",
    panels=(
        PanelSpec("force_canvas", "Curva de fuerza", _force_canvas),
        PanelSpec("pipeline", "Pipeline", _pipeline, area="bottom"),
        PanelSpec("map_canvas", "Mapa", _map_canvas),
        PanelSpec("histogram", "Histograma", _histogram, area="right"),
        PanelSpec("batch_table", "Batch", _batch_table),
    ),
    perspectives=(
        PerspectiveSpec(
            "force", "Curva de fuerza", ("navigator", "force_canvas", "inspector", "pipeline")
        ),
        PerspectiveSpec("map", "Mapa", ("navigator", "map_canvas", "inspector", "histogram")),
        PerspectiveSpec("batch", "Batch", ("navigator", "batch_table", "log")),
    ),
    wire=_wire_force,
)

_FIGURE = ModuleSpec(
    name="figure",
    panels=(PanelSpec("figure_editor", "Figura", _figure),),
    perspectives=(PerspectiveSpec("figure", "Figura", ("figure_editor", "inspector")),),
)

_VIEW3D = ModuleSpec(
    name="view3d",
    panels=(PanelSpec("view3d", "Vista 3D", _view3d),),
    perspectives=(PerspectiveSpec("view3d", "Vista 3D", ("view3d",)),),
)

_SIMULATOR = ModuleSpec(
    name="simulator",
    panels=(PanelSpec("simulator", "Simulador", _simulator),),
    perspectives=(PerspectiveSpec("simulator", "Simulador", ("simulator",)),),
)

#: Los módulos que trae Fathom, en orden de la barra de perspectivas.
BUILTIN_MODULES: tuple[ModuleSpec, ...] = (_CORE, _IMAGE, _FORCE, _FIGURE, _VIEW3D, _SIMULATOR)
