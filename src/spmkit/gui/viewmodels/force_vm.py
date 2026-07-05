"""ViewModel de espectroscopía de fuerza — estado observable entre core y paneles.

Mantiene el force-volume activo, la curva actual, la receta y los resultados; emite
señales Qt cuando algo cambia. Aplica los refinamientos v2:

* **Caché LRU de curvas**: al hacer *scrubbing* solo se re-renderiza la curva (barato),
  sin recalcular el pipeline.
* **Ajuste con debounce**: el pipeline se re-ejecuta con un ``QTimer`` de 150 ms tras
  soltar el cursor, y sus resultados se cachean por curva.

No implementa física: delega en el pipeline puro del core.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from spmkit.core.models import ForceCurve, ForceVolume
from spmkit.core.pipeline import Recipe, Step, run

#: Parámetros por defecto del pipeline de ajuste (fuente única de la receta).
DEFAULT_PARAMS: dict[str, Any] = {
    "model": "sphere",
    "tip_radius": 10e-9,
    "poisson": 0.3,
    "half_angle": None,  # rad; sólo modelo cone
    "invols": None,  # m/V; None = usar metadatos
    "spring_constant": None,  # N/m; None = usar metadatos
    "smooth_window": 0,  # ventana Savitzky-Golay (0/<3 = sin suavizado)
    "fit_min": None,  # m; ventana de ajuste manual (con fit_max)
    "fit_max": None,
}


def build_recipe(params: dict[str, Any]) -> Recipe:
    """Construye la :class:`Recipe` de ajuste desde el dict de parámetros (pura)."""
    cal: dict[str, Any] = {}
    if params.get("invols"):
        cal["invols"] = params["invols"]
    if params.get("spring_constant"):
        cal["spring_constant"] = params["spring_constant"]
    fit: dict[str, Any] = {
        "model": params["model"],
        "tip_radius": params["tip_radius"],
        "poisson": params["poisson"],
    }
    if params["model"] == "cone" and params.get("half_angle") is not None:
        fit["half_angle"] = params["half_angle"]
    fmin, fmax = params.get("fit_min"), params.get("fit_max")
    if fmin is not None and fmax is not None:
        fit["fit_range"] = (fmin, fmax)
    steps = [Step(op="calibrate", params=cal)]
    window = int(params.get("smooth_window") or 0)
    if window >= 3:
        steps.append(Step(op="smooth", params={"window": window}))
    steps.append(Step(op="find_contact_point"))
    steps.append(Step(op="fit_elasticity", params=fit, condition="contact_detected"))
    return Recipe(steps=tuple(steps))


#: Receta por defecto (Hertz esférico con detección de contacto).
DEFAULT_RECIPE = build_recipe(DEFAULT_PARAMS)

_FIT_DEBOUNCE_MS = 150
_CURVE_CACHE_MAX = 64


class ForceViewModel(QObject):
    """Estado observable de la perspectiva de curva de fuerza."""

    volumeChanged = pyqtSignal(int)  # nuevo force-volume cargado (n_curves)
    curveChanged = pyqtSignal(int)  # nuevo índice de curva (render-only)
    resultsChanged = pyqtSignal(dict)  # contexto del pipeline (ajuste)
    recipeChanged = pyqtSignal(object)  # nueva Recipe
    statusChanged = pyqtSignal(str)  # mensaje para la barra de estado

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._volume: ForceVolume | None = None
        self._index = 0
        self._params: dict[str, Any] = dict(DEFAULT_PARAMS)
        self._recipe = DEFAULT_RECIPE
        self._curve_cache: dict[int, Any] = {}
        self._curve_order: list[int] = []
        self._results_cache: dict[int, dict[str, Any]] = {}
        # Curva calibrada que devuelve el pipeline (para dibujar fuerza vs separación).
        # ponytail: sin cota; para force-volumes enormes acotarlo o no cachear (Fase D).
        self._result_curve_cache: dict[int, ForceCurve] = {}
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(_FIT_DEBOUNCE_MS)
        self._fit_timer.timeout.connect(self._run_fit)

    # ---- estado ----
    @property
    def n_curves(self) -> int:
        return self._volume.n_curves if self._volume is not None else 0

    @property
    def index(self) -> int:
        return self._index

    @property
    def volume(self) -> ForceVolume | None:
        return self._volume

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    @property
    def params(self) -> dict[str, Any]:
        """Copia de los parámetros del pipeline de ajuste."""
        return dict(self._params)

    def set_param(self, key: str, value: Any) -> None:
        """Actualiza un parámetro del ajuste y reconstruye la receta (re-ajuste)."""
        if self._params.get(key) == value:
            return
        self._params[key] = value
        self.set_recipe(build_recipe(self._params))

    def set_params(self, **kwargs: Any) -> None:
        """Actualiza varios parámetros de una vez (una sola reconstrucción)."""
        changed = False
        for key, value in kwargs.items():
            if self._params.get(key) != value:
                self._params[key] = value
                changed = True
        if changed:
            self.set_recipe(build_recipe(self._params))

    def set_volume(self, volume: ForceVolume) -> None:
        """Carga un force-volume nuevo y activa la primera curva."""
        self._volume = volume
        self._curve_cache.clear()
        self._curve_order.clear()
        self._results_cache.clear()
        self._result_curve_cache.clear()
        self._index = 0
        self.volumeChanged.emit(volume.n_curves)
        self.curveChanged.emit(0)
        self._schedule_fit()

    def current_curve(self) -> Any:
        """Devuelve la curva activa cruda (con caché LRU)."""
        return self._curve(self._index)

    def result_curve(self) -> ForceCurve | None:
        """Curva calibrada del pipeline para el índice actual (o ``None`` si aún no)."""
        return self._result_curve_cache.get(self._index)

    def current_results(self) -> dict[str, Any]:
        """Contexto del pipeline (resultados) cacheado para el índice actual."""
        return dict(self._results_cache.get(self._index, {}))

    def set_curve(self, index: int) -> None:
        """Cambia la curva activa (render inmediato; ajuste con debounce)."""
        if self._volume is None or not (0 <= index < self._volume.n_curves):
            return
        self._index = index
        self.curveChanged.emit(index)
        self._schedule_fit()

    def set_recipe(self, recipe: Recipe) -> None:
        """Actualiza la receta e invalida los resultados cacheados."""
        self._recipe = recipe
        self._results_cache.clear()
        self._result_curve_cache.clear()
        self.recipeChanged.emit(recipe)
        self._schedule_fit()

    def run_fit_now(self) -> None:
        """Fuerza el ajuste de inmediato (sin esperar el debounce)."""
        self._fit_timer.stop()
        self._run_fit()

    # ---- internos ----
    def _curve(self, index: int) -> Any:
        if index in self._curve_cache:
            return self._curve_cache[index]
        assert self._volume is not None
        curve = self._volume.curve(index)
        self._curve_cache[index] = curve
        self._curve_order.append(index)
        if len(self._curve_order) > _CURVE_CACHE_MAX:
            evicted = self._curve_order.pop(0)
            self._curve_cache.pop(evicted, None)
        return curve

    def _schedule_fit(self) -> None:
        self._fit_timer.start()

    def _run_fit(self) -> None:
        if self._volume is None:
            return
        index = self._index
        if index in self._results_cache:
            self.resultsChanged.emit(self._results_cache[index])
            return
        try:
            result, ctx = run(self._recipe, self._curve(index))
        except Exception as exc:  # noqa: BLE001 - se muestra, nunca se traga
            self.statusChanged.emit(f"ajuste falló: {exc}")
            self.resultsChanged.emit({})
            return
        self._results_cache[index] = ctx
        self._result_curve_cache[index] = result
        self.resultsChanged.emit(ctx)
