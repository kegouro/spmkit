"""ViewModel de SMFS (espectroscopía de fuerza de molécula única).

Corre el pipeline de cadena del ``core`` (``correct_retract_baseline`` → ``detect_events`` →
``fit_wlc``/``fit_fjc`` con QC) sobre la **rama de retracción** de la curva activa del
:class:`ForceViewModel`. A diferencia de la perspectiva de elasticidad, SMFS no necesita
detectar contacto ni ajustar Hertz: solo requiere el retract **calibrado** (fuerza +
separación), así que aplica una receta ``calibrate``-only (no-op si el archivo ya trae fuerza)
y delega en ``core.analysis.chain``. Barato (una curva) → recalcula al cambiar de curva.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import chain
from spmkit.core.pipeline import Recipe, Step, run
from spmkit.gui.viewmodels.force_vm import ForceViewModel

#: Parámetros del pipeline SMFS expuestos en la UI (nada hardcodeado). Fuente única de defaults.
DEFAULT_SMFS_PARAMS: dict[str, float] = {
    "min_r_squared": 0.95,  # QC: descarta ajustes por debajo
    "min_prominence_sigma": 5.0,  # detección: prominencia mínima sobre el valle (×σ)
    "min_height_sigma": 5.0,  # detección: altura mínima sobre el baseline (×σ)
    "baseline_fraction": 0.3,  # fracción de la cola libre para σ y corrección de base
    "temperature": 298.0,  # K; modelos entrópicos WLC/FJC
}


@dataclass(frozen=True)
class SmfsResult:
    """Resultado de SMFS listo para dibujar: la curva corregida, los eventos y sus overlays."""

    separation: np.ndarray  # separación ordenada (m)
    force: np.ndarray  # fuerza corregida de línea base (N)
    events: list[chain.EventFit]  # eventos aceptados (evento + ajuste)
    overlays: list[tuple[np.ndarray, np.ndarray]]  # (sep, fuerza) del modelo por evento
    model: str


class SmfsViewModel(QObject):
    """Estado observable del análisis SMFS de la curva activa."""

    resultChanged = pyqtSignal(object)  # SmfsResult (o None al invalidar)
    statusChanged = pyqtSignal(str)
    modelChanged = pyqtSignal(str)  # "wlc" | "fjc"
    paramsChanged = pyqtSignal(dict)  # umbrales editados en la UI
    wlcModelChanged = pyqtSignal(str)  # "bouchiat" | "marko_siggia"

    def __init__(self, force_vm: ForceViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._force_vm = force_vm
        self._model = "wlc"
        self._wlc_model = "bouchiat"  # variante del WLC
        self._params: dict[str, float] = dict(DEFAULT_SMFS_PARAMS)
        self._result: SmfsResult | None = None
        force_vm.curveChanged.connect(lambda _i: self.compute())
        force_vm.volumeChanged.connect(lambda _n: self.compute())

    @property
    def result(self) -> SmfsResult | None:
        return self._result

    @property
    def model(self) -> str:
        return self._model

    @property
    def wlc_model(self) -> str:
        return self._wlc_model

    def set_wlc_model(self, variant: str) -> None:
        """Variante del WLC (``"bouchiat"``/``"marko_siggia"``); recalcula si el modelo es WLC."""
        if variant not in ("bouchiat", "marko_siggia") or variant == self._wlc_model:
            return
        self._wlc_model = variant
        self.wlcModelChanged.emit(variant)
        if self._model == "wlc":
            self.compute()

    @property
    def params(self) -> dict[str, float]:
        """Copia de los umbrales del pipeline (para poblar los controles de la UI)."""
        return dict(self._params)

    def set_model(self, model: str) -> None:
        """Cambia el modelo de cadena (``"wlc"``/``"fjc"``) y recalcula."""
        if model not in ("wlc", "fjc") or model == self._model:
            return
        self._model = model
        self.modelChanged.emit(model)
        self.compute()

    def set_param(self, key: str, value: float) -> None:
        """Actualiza un umbral del pipeline (R², sigmas, fracción) y recalcula."""
        if key not in self._params or self._params[key] == value:
            return
        self._params[key] = float(value)
        self.paramsChanged.emit(dict(self._params))
        self.compute()

    def _analyze(self, curve: object) -> tuple[np.ndarray, np.ndarray, list[chain.EventFit]]:
        """Corre baseline → detección → ajuste sobre el retract de una ``ForceCurve`` cruda.

        Calibra (no-op si ya trae fuerza), ordena por separación, corrige base y ajusta con los
        parámetros actuales. Devuelve ``(sep, corrected, events)``; lanza ``ValueError`` si no hay
        retract calibrado.
        """
        calibrated = run(_calibrate_recipe(self._force_vm.params), curve)[0]
        retract = calibrated.retract
        if retract is None or retract.force is None or retract.separation is None:
            raise ValueError("la curva no tiene retracción calibrada")
        sep = np.asarray(retract.separation, dtype=np.float64)
        force = np.asarray(retract.force, dtype=np.float64)
        order = np.argsort(sep)  # el pipeline espera separación creciente
        sep, force = sep[order], force[order]
        p = self._params
        bf = p["baseline_fraction"]
        corrected = chain.correct_retract_baseline(sep, force, baseline_fraction=bf)
        events = chain.fit_chain_events(
            sep,
            corrected,
            model=self._model,
            correct_baseline=False,
            baseline_fraction=bf,
            min_prominence_sigma=p["min_prominence_sigma"],
            min_height_sigma=p["min_height_sigma"],
            min_r_squared=p["min_r_squared"],
            temperature=p["temperature"],
            wlc_model=self._wlc_model,
        )
        return sep, corrected, events

    def compute(self) -> None:
        """Corre el pipeline SMFS sobre el retract de la curva activa; emite ``resultChanged``."""
        vm = self._force_vm
        if vm.volume is None:
            self._emit(None)
            return
        try:
            sep, corrected, events = self._analyze(vm.current_curve())
        except Exception as exc:  # noqa: BLE001 - curva degenerada: se informa, no tumba la app
            self.statusChanged.emit(f"SMFS falló: {exc}")
            self._emit(None)
            return
        overlays = [self._overlay(sep, corrected, ef) for ef in events]
        self.statusChanged.emit(f"{len(events)} evento(s) — modelo {self._model.upper()}")
        self._emit(SmfsResult(sep, corrected, events, overlays, self._model))

    def aggregate_contours(self) -> np.ndarray:
        """Longitudes de contorno (m) de **todos** los eventos aceptados de **todo** el volumen.

        Corre el pipeline SMFS por cada curva del force-volume (población para el histograma).
        Las curvas sin retract o degeneradas se saltan.
        """
        vm = self._force_vm
        if vm.volume is None:
            return np.empty(0, dtype=np.float64)
        contours: list[float] = []
        for i in range(vm.n_curves):
            try:
                _, _, events = self._analyze(vm.volume.curve(i))
            except Exception:  # noqa: BLE001 - curva sin retract/degenerada: se salta
                continue
            contours.extend(ef.fit.contour_length for ef in events)
        return np.asarray(contours, dtype=np.float64)

    def export_events_csv(self, path: str) -> int:
        """Exporta los eventos de la curva activa a CSV (FAIR). Devuelve el nº de filas escritas."""
        result = self._result
        if result is None or not result.events:
            return 0
        import csv

        second = "kuhn_length_m" if self._model == "fjc" else "persistence_length_m"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["evento", "separacion_m", "fuerza_N", "contorno_m", second, "r_squared"]
            )
            for i, ef in enumerate(result.events, start=1):
                fit = ef.fit
                second_val = fit.kuhn_length if self._model == "fjc" else fit.persistence_length
                writer.writerow(
                    [
                        i,
                        ef.event.separation,
                        ef.event.force,
                        fit.contour_length,
                        second_val,
                        fit.r_squared,
                    ]
                )
        return len(result.events)

    def _overlay(
        self, sep: np.ndarray, force: np.ndarray, ef: chain.EventFit
    ) -> tuple[np.ndarray, np.ndarray]:
        """Curva (sep, fuerza) del modelo ajustado para superponer sobre el evento."""
        sl = slice(ef.event.start_index, ef.event.peak_index + 1)
        seg_sep = sep[sl]
        x = seg_sep - seg_sep[0]
        fit = ef.fit
        if self._model == "wlc":
            f_fit = chain.wlc_force(x, fit.contour_length, fit.persistence_length, model=fit.model)
            return seg_sep, f_fit
        # FJC: el modelo es x(F) → evaluamos extensión sobre la fuerza del tramo
        f_seg = force[sl]
        x_fit = chain.fjc_extension(f_seg, fit.contour_length, fit.kuhn_length or 0.0)
        return seg_sep[0] + x_fit, f_seg

    def _emit(self, result: SmfsResult | None) -> None:
        self._result = result
        self.resultChanged.emit(result)


def _calibrate_recipe(params: dict) -> Recipe:
    """Receta ``calibrate``-only con los parámetros de calibración del ForceViewModel."""
    cal: dict = {}
    if params.get("invols"):
        cal["invols"] = params["invols"]
    if params.get("spring_constant"):
        cal["spring_constant"] = params["spring_constant"]
    return Recipe(steps=(Step(op="calibrate", params=cal),))
