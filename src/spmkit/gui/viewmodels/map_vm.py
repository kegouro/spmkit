"""ViewModel del mapa de propiedades (force-volume) — corre el pipeline por curva.

Comparte el :class:`ForceViewModel` como *hub* de la curva activa: hacer clic en un
píxel del mapa llama a ``force_vm.set_curve`` (linked brushing map→curva), y el panel
del mapa escucha ``force_vm.curveChanged`` para mover su cruz (curva→map).

El cálculo del mapa es costoso (un ajuste por curva), así que va en un :class:`Task`
fuera del hilo de UI; ``compute_now`` corre sincrónico para los tests.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis.forcevolume import DEFAULT_KEYS, VolumeResult, analyze_volume
from spmkit.core.analysis.forcevolume_fast import elasticity_map
from spmkit.gui.runtime.tasks import Task, run_task
from spmkit.gui.viewmodels.force_vm import ForceViewModel

#: Propiedades mapeables: clave → (etiqueta, factor de escala display, unidad).
PROPERTIES: dict[str, tuple[str, float, str]] = {
    "young_modulus": ("Módulo E", 1e-3, "kPa"),
    "adhesion": ("Adhesión", 1e9, "nN"),
    "dissipation": ("Disipación", 1e15, "fJ"),
    "r_squared": ("R²", 1.0, ""),
    "contact_point": ("Contacto", 1e9, "nm"),
    "max_force": ("Fuerza máx", 1e9, "nN"),
    "max_indentation": ("δ máx", 1e9, "nm"),
}


class MapViewModel(QObject):
    """Estado observable del mapa de propiedades de un force-volume."""

    mapReady = pyqtSignal(object)  # VolumeResult (o None al invalidar)
    keyChanged = pyqtSignal(str)  # propiedad activa
    taskStarted = pyqtSignal(object)  # Task lanzado (el shell lo engancha a la barra)
    statusChanged = pyqtSignal(str)
    computingChanged = pyqtSignal(bool)

    def __init__(self, force_vm: ForceViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._force_vm = force_vm
        self._result: VolumeResult | None = None
        self._key = "young_modulus"
        self._task: Task | None = None
        force_vm.volumeChanged.connect(self._on_volume_changed)

    # ---- estado ----
    @property
    def result(self) -> VolumeResult | None:
        return self._result

    @property
    def key(self) -> str:
        return self._key

    @property
    def keys(self) -> tuple[str, ...]:
        return DEFAULT_KEYS

    def set_key(self, key: str) -> None:
        if key != self._key:
            self._key = key
            self.keyChanged.emit(key)

    def select(self, index: int) -> None:
        """Linked brushing: selecciona la curva ``index`` en el hub compartido."""
        self._force_vm.set_curve(index)

    # ---- cálculo ----
    def _fast_kwargs(self, backend: str) -> dict:
        """Parámetros del ajuste (del pipeline panel) para la ruta vectorizada."""
        p = self._force_vm.params
        kw: dict = {
            "model": p["model"],
            "tip_radius": p["tip_radius"],
            "poisson": p["poisson"],
            "backend": backend,
        }
        if p.get("half_angle") is not None:
            kw["half_angle"] = p["half_angle"]
        return kw

    def _nonstandard(self) -> bool:
        """¿La receta usa opciones que la ruta rápida no honra (suavizado/región/cal)?"""
        p = self._force_vm.params
        return bool(
            int(p.get("smooth_window") or 0) >= 3
            or p.get("fit_min") is not None
            or p.get("invols")
            or p.get("spring_constant")
        )

    def compute_now(self, engine: str = "fast_cpu") -> None:
        """Calcula el mapa de forma sincrónica (tests / volúmenes chicos)."""
        volume = self._force_vm.volume
        if volume is None:
            return
        if engine == "pipeline":
            self._result = analyze_volume(volume, self._force_vm.recipe)
        else:
            backend = "gpu" if engine == "fast_gpu" else "cpu"
            self._result = elasticity_map(volume, **self._fast_kwargs(backend))
        self.mapReady.emit(self._result)

    def compute(self, engine: str = "fast_cpu", parallel: bool = False) -> None:
        """Calcula el mapa en un hilo worker; emite ``mapReady`` al terminar.

        ``engine``: ``"fast_cpu"``/``"fast_gpu"`` (vectorizado, precisión de máquina) o
        ``"pipeline"`` (por curva, respeta suavizado/región/calibración, todas las
        propiedades). Si la receta es no estándar, la ruta rápida cae al pipeline.
        """
        volume = self._force_vm.volume
        if volume is None:
            self.statusChanged.emit("no hay force-volume cargado")
            return
        if self._task is not None:
            return  # ya hay un cálculo en curso
        if engine != "pipeline" and self._nonstandard():
            self.statusChanged.emit("suavizado/región/calibración activos → uso el pipeline")
            engine = "pipeline"
        if engine == "pipeline":
            task = Task(
                analyze_volume,
                volume,
                self._force_vm.recipe,
                parallel=parallel,
                provide_progress=True,
            )
        else:
            backend = "gpu" if engine == "fast_gpu" else "cpu"
            task = Task(elasticity_map, volume, **self._fast_kwargs(backend))
        task.signals.done.connect(self._on_done)
        task.signals.error.connect(lambda exc: self.statusChanged.emit(f"mapa falló: {exc}"))
        task.signals.finished.connect(self._on_finished)
        self._task = task
        self.computingChanged.emit(True)
        self.taskStarted.emit(task)  # el shell lo engancha a la barra de progreso global
        run_task(task)

    def _on_done(self, result: object) -> None:
        self._result = result if isinstance(result, VolumeResult) else None
        self.mapReady.emit(self._result)

    def _on_finished(self) -> None:
        self._task = None
        self.computingChanged.emit(False)

    def _on_volume_changed(self, _n: int) -> None:
        self._result = None
        self.mapReady.emit(None)
        self.statusChanged.emit("mapa sin calcular")
