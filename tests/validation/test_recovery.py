"""Gate de validación numérica: recuperar parámetros conocidos de datos sintéticos.

Filosofía (revisión senior): antes de UI o features nuevas, el núcleo debe **recuperar los
parámetros con los que se generó el dato**, con error acotado, incluso con ruido conocido.
Si el ajuste no recupera E dentro de tolerancia, el código no pasa — no importa qué botón
tenga. Este archivo es el primer ladrillo de ese gate (modelos que ya existen); se extenderá
con Lp/Lc (WLC/FJC) cuando esos modelos entren.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import forcecurve
from spmkit.core.analysis.forcevolume_fast import elasticity_map
from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume

_R = 10e-9  # radio de punta (m)
_NU = 0.3  # Poisson


def _synthetic_indentation(
    young: float,
    model: str = "sphere",
    n: int = 400,
    contact_sep: float = 3e-7,
    noise_frac: float = 0.0,
    seed: int = 0,
    half_angle: float = np.deg2rad(20.0),
    adhesion: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Genera (separación, fuerza) con módulo conocido para un modelo de contacto.

    Fuera de contacto: fuerza = 0 (línea base plana). En contacto: la ley del modelo.
    ``noise_frac`` añade ruido gaussiano relativo a la fuerza máxima (ruido conocido).
    """
    sep = np.linspace(6e-7, 0.0, n)
    delta = np.clip(contact_sep - sep, 0.0, None)
    e_star = young / (1.0 - _NU**2)
    if model in ("sphere", "paraboloid", "dmt"):
        force = (4.0 / 3.0) * e_star * np.sqrt(_R) * delta**1.5
    elif model == "cone":
        force = (2.0 / np.pi) * e_star * np.tan(half_angle) * delta**2
    else:  # pragma: no cover
        raise ValueError(model)
    if model == "dmt":
        force = force - adhesion  # DMT: offset de adhesión constante
    if noise_frac > 0.0:
        rng = np.random.default_rng(seed)
        force = force + rng.normal(0.0, noise_frac * float(force.max()), size=force.shape)
    return sep, force


@pytest.mark.parametrize("model", ["sphere", "cone"])
def test_recupera_modulo_sin_ruido(model: str) -> None:
    """Sin ruido, el ajuste debe recuperar E a <1% (es una regresión lineal exacta)."""
    young = 1.0e6
    sep, force = _synthetic_indentation(young, model=model)
    fit = forcecurve.fit_force_curve(sep, force, model=model, tip_radius=_R, poisson=_NU)
    rel_err = abs(fit.young_modulus - young) / young
    assert rel_err < 0.01, f"{model}: E recuperado {fit.young_modulus:.3e} vs {young:.3e}"
    assert fit.r_squared > 0.999


@pytest.mark.parametrize("seed", [0, 3, 6])
def test_recupera_modulo_con_ruido(seed: int) -> None:
    """Con 1% de ruido conocido, E se recupera a <2% gracias al **ajuste conjunto** del
    punto de contacto (Alpha #1). Con el umbral k·σ, el mismo dato sesga E ~+30%.
    """
    young = 5.0e5
    sep, force = _synthetic_indentation(young, model="sphere", noise_frac=0.01, seed=seed)
    fit = forcecurve.fit_force_curve(sep, force, model="sphere", tip_radius=_R, poisson=_NU)
    assert abs(fit.young_modulus - young) / young < 0.02


def test_ajuste_conjunto_vence_al_umbral_bajo_ruido() -> None:
    """Regresión del fix: el contacto por ajuste conjunto debe sesgar mucho menos que el
    umbral k·σ bajo ruido (protege el fix de Alpha #1 de futuras regresiones)."""
    young = 5.0e5
    sep, force = _synthetic_indentation(young, model="sphere", noise_frac=0.01, seed=1)
    e_joint = forcecurve.fit_force_curve(
        sep, force, model="sphere", tip_radius=_R, poisson=_NU, contact_method="joint"
    ).young_modulus
    e_thr = forcecurve.fit_force_curve(
        sep, force, model="sphere", tip_radius=_R, poisson=_NU, contact_method="threshold"
    ).young_modulus
    err_joint = abs(e_joint - young) / young
    err_thr = abs(e_thr - young) / young
    assert err_joint < 0.02 and err_joint < err_thr / 5  # el conjunto es ≫ mejor


# NOTA: recuperación DMT/JKR con adhesión requiere un sintético con **snap-in** realista
# (la detección de contacto DMT usa el mínimo/snap-in). Mi sintético de baseline plana no lo
# tiene, así que se difiere a la tanda que construya el generador de snap-in + JKR validado.


def test_recupera_mapa_de_modulos() -> None:
    """La ruta vectorizada (elasticity_map) recupera un gradiente de módulos conocidos."""
    moduli = [3.0e5, 6.0e5, 1.2e6, 2.4e6]
    curves = []
    for e in moduli:
        sep, force = _synthetic_indentation(e, model="sphere")
        z = np.zeros_like(sep)
        seg = ForceSegment(
            segment_type="extend",
            direction="approach",
            raw_height=sep,
            raw_deflection=z,
            deflection=z,
            force=force,
            separation=sep,
            state="force_n",
        )
        curves.append(ForceCurve(segments=(seg, seg)))
    vol = ForceVolume.from_curves(tuple(curves), grid_shape=(1, 4), x_range=1e-6, y_range=1e-6)
    result = elasticity_map(vol, tip_radius=_R, poisson=_NU, model="sphere")
    assert result.n_ok == 4
    recovered = np.asarray(result.maps["young_modulus"]).ravel()
    for got, want in zip(recovered, moduli, strict=True):
        assert abs(got - want) / want < 0.02, f"mapa: {got:.3e} vs {want:.3e}"


# --------------------------------------------------------------------- cadena (SMFS)

_L_TRUE, _LP_TRUE = 100e-9, 0.4e-9  # contorno 100 nm, persistencia 0.4 nm (proteína)


def _wlc_curve(model: str, noise_frac: float = 0.0, seed: int = 0):
    from spmkit.core.analysis import chain

    x = np.linspace(0.30 * _L_TRUE, 0.95 * _L_TRUE, 120)
    f = chain.wlc_force(x, _L_TRUE, _LP_TRUE, model=model)
    if noise_frac > 0.0:
        rng = np.random.default_rng(seed)
        f = f + rng.normal(0.0, noise_frac * float(f.max()), f.shape)
    return x, f


@pytest.mark.parametrize("model", ["marko_siggia", "bouchiat"])
def test_recupera_wlc_sin_ruido(model: str) -> None:
    """WLC: sin ruido recupera contorno L y persistencia lp a <1% (ajuste separable exacto)."""
    from spmkit.core.analysis import chain

    x, f = _wlc_curve(model)
    fit = chain.fit_wlc(x, f, model=model)
    assert abs(fit.contour_length - _L_TRUE) / _L_TRUE < 0.01
    assert abs(fit.persistence_length - _LP_TRUE) / _LP_TRUE < 0.01
    assert fit.r_squared > 0.999


def test_recupera_wlc_con_ruido() -> None:
    """WLC con 2% de ruido: L a <2%, lp a <5% (bien condicionado como el contacto)."""
    from spmkit.core.analysis import chain

    x, f = _wlc_curve("bouchiat", noise_frac=0.02, seed=0)
    fit = chain.fit_wlc(x, f, model="bouchiat")
    assert abs(fit.contour_length - _L_TRUE) / _L_TRUE < 0.02
    assert abs(fit.persistence_length - _LP_TRUE) / _LP_TRUE < 0.05


_B_TRUE = 0.8e-9  # longitud de Kuhn 0.8 nm (lp = b/2 = 0.4 nm, consistente con el WLC)


def _fjc_curve(noise_frac: float = 0.0, seed: int = 0):
    """(extension, force) de un FJC con L/b conocidos. u_max≈8 → régimen no lineal claro."""
    from spmkit.core.analysis import chain

    kt = chain._KB * 298.0
    f_max = 8.0 * kt / _B_TRUE  # u_max = F_max·b/k_BT ≈ 8
    f = np.linspace(0.02 * f_max, f_max, 120)
    x = chain.fjc_extension(f, _L_TRUE, _B_TRUE)
    if noise_frac > 0.0:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0.0, noise_frac * float(x.max()), x.shape)
    return x, f


def test_recupera_fjc_sin_ruido() -> None:
    """FJC: sin ruido recupera contorno L y Kuhn b a <1% (ajuste separable exacto)."""
    from spmkit.core.analysis import chain

    x, f = _fjc_curve()
    fit = chain.fit_fjc(x, f)
    assert fit.model == "fjc"
    assert abs(fit.contour_length - _L_TRUE) / _L_TRUE < 0.01
    assert abs(fit.kuhn_length - _B_TRUE) / _B_TRUE < 0.01
    assert fit.persistence_length == fit.kuhn_length / 2.0  # invariante lp = b/2
    assert fit.r_squared > 0.999


def test_recupera_fjc_con_ruido() -> None:
    """FJC con 2% de ruido: L a <2%, b a <5% (bien condicionado como el WLC)."""
    from spmkit.core.analysis import chain

    x, f = _fjc_curve(noise_frac=0.02, seed=0)
    fit = chain.fit_fjc(x, f)
    assert abs(fit.contour_length - _L_TRUE) / _L_TRUE < 0.02
    assert abs(fit.kuhn_length - _B_TRUE) / _B_TRUE < 0.05


def test_corrige_baseline_retract_recupera_plano_y_preserva_evento() -> None:
    """La corrección de retract debe quitar un artefacto lineal (offset+tilt) conocido:
    la cola libre queda ~0 y la altura del evento se preserva (paso previo a los ajustes)."""
    from spmkit.core.analysis import chain

    sep = np.linspace(0.0, 600e-9, 400)
    # Evento WLC entre 100–300 nm; base plana (0) antes y en la cola de gran separación.
    evt = (sep >= 100e-9) & (sep <= 300e-9)
    clean = np.zeros_like(sep)
    clean[evt] = chain.wlc_force(sep[evt] - 100e-9, 220e-9, _LP_TRUE)
    peak_clean = float(clean.max())

    slope, offset = 3e-3, 8e-12  # deflexión virtual: N/m de tilt + offset del fotodetector
    rng = np.random.default_rng(0)
    raw = clean + slope * sep + offset + rng.normal(0.0, 0.01 * peak_clean, sep.shape)

    corr = chain.correct_retract_baseline(sep, raw)
    far = np.argsort(sep)[-120:]  # cola libre (gran separación)
    assert abs(float(corr[far].mean())) < 0.05 * peak_clean  # base ~0
    assert float(np.std(corr[far])) < 0.05 * peak_clean  # solo ruido, sin tilt
    # el pico del evento se conserva (la recta restada es ~plana donde está el evento)
    assert abs(float(corr[evt].max()) - peak_clean) / peak_clean < 0.1


# --------------------------------------------------------- detección de eventos multi-pico

_SEG_LEN, _CONTOUR = 80e-9, 82e-9  # cada evento ocupa ~80 nm; contorno 82 nm (sube en todo)


def _sawtooth(n_events: int = 4, noise_frac: float = 0.0, seed: int = 0):
    """Retract sintético tipo *sawtooth*: N eventos WLC (sube → ruptura → 0) + cola libre."""
    from spmkit.core.analysis import chain

    seps, forces, peaks = [], [], []
    for k in range(n_events):
        start = k * _SEG_LEN
        x = np.linspace(0.0, 0.9 * _CONTOUR, 100)  # extensión dentro del evento
        seps.append(start + x)
        forces.append(chain.wlc_force(x, _CONTOUR, _LP_TRUE))
        peaks.append(start + float(x[-1]))  # separación de la ruptura (pico)
    tail = np.linspace(seps[-1][-1], seps[-1][-1] + 160e-9, 200)  # cola libre para σ
    seps.append(tail)
    forces.append(np.zeros_like(tail))
    sep = np.concatenate(seps)
    f = np.concatenate(forces)
    if noise_frac > 0.0:
        rng = np.random.default_rng(seed)
        f = f + rng.normal(0.0, noise_frac * float(f.max()), f.shape)
    return sep, f, np.array(peaks)


def test_detecta_eventos_multipico() -> None:
    """Detecta los N eventos de un sawtooth ruidoso, cada pico cerca de la ruptura real."""
    from spmkit.core.analysis import chain

    sep, f, peaks_true = _sawtooth(n_events=4, noise_frac=0.01, seed=0)
    events = chain.detect_events(sep, f)
    assert len(events) == 4
    got = np.array([e.separation for e in events])
    assert np.all(np.abs(got - peaks_true) < 2e-9)  # pico bien localizado (<2 nm)
    assert all(e.prominence > 0 for e in events)


def test_ruido_puro_no_genera_eventos() -> None:
    """Baseline puro con ruido: la detección por prominencia no inventa rupturas."""
    from spmkit.core.analysis import chain

    rng = np.random.default_rng(1)
    sep = np.linspace(0.0, 500e-9, 400)
    f = rng.normal(0.0, 1e-11, sep.shape)  # solo ruido gaussiano
    assert chain.detect_events(sep, f) == []


def test_evento_detectado_recupera_su_contorno() -> None:
    """El tramo [start, peak] de un evento detectado, ajustado con WLC, recupera su contorno."""
    from spmkit.core.analysis import chain

    sep, f, _ = _sawtooth(n_events=3, noise_frac=0.0)
    events = chain.detect_events(sep, f)
    assert len(events) == 3
    e = events[0]
    x = sep[e.start_index : e.peak_index + 1] - sep[e.start_index]
    fit = chain.fit_wlc(x, f[e.start_index : e.peak_index + 1])
    assert abs(fit.contour_length - _CONTOUR) / _CONTOUR < 0.05


def _sawtooth_varying(contours, noise_frac=0.0, tilt=0.0, offset=0.0, seed=0):
    """Sawtooth con un contorno distinto por evento (+ tilt/offset de deflexión virtual)."""
    from spmkit.core.analysis import chain

    seps, forces = [], []
    start = 0.0
    for c in contours:
        x = np.linspace(0.0, 0.9 * c, 130)
        seps.append(start + x)
        forces.append(chain.wlc_force(x, c, _LP_TRUE))
        start = start + 0.9 * c + 12e-9  # gap tras la ruptura, antes del próximo evento
    tail = np.linspace(start, start + 200e-9, 220)
    seps.append(tail)
    forces.append(np.zeros_like(tail))
    sep = np.concatenate(seps)
    f = np.concatenate(forces)
    peak = float(f.max())
    if noise_frac > 0.0 or tilt or offset:
        rng = np.random.default_rng(seed)
        f = f + tilt * sep + offset + rng.normal(0.0, noise_frac * peak, sep.shape)
    return sep, f


def test_pipeline_smfs_recupera_contornos_con_tilt() -> None:
    """Pipeline completo (baseline → detectar → ajustar + QC): recupera el contorno de cada
    evento de un sawtooth con tilt de deflexión virtual y ruido. Sin corregir baseline, falla."""
    from spmkit.core.analysis import chain

    contours = [70e-9, 95e-9, 120e-9]
    sep, f = _sawtooth_varying(contours, noise_frac=0.01, tilt=2e-3, offset=6e-12, seed=0)

    results = chain.fit_chain_events(sep, f, model="wlc")  # corrige baseline internamente
    assert len(results) == 3
    got = sorted(r.fit.contour_length for r in results)
    for recovered, want in zip(got, contours, strict=True):
        assert abs(recovered - want) / want < 0.06
    assert all(r.fit.r_squared >= 0.95 for r in results)  # el QC se aplica

    # el tilt (mayor que el pico) arruina detección/ajuste si no se corrige la base primero
    bad = chain.fit_chain_events(sep, f, model="wlc", correct_baseline=False)
    assert len(bad) < 3


def test_analyze_retract_desde_forcecurve() -> None:
    """El adaptador de modelo corre el pipeline sobre la rama de retract de una ForceCurve."""
    from spmkit.core.analysis import chain
    from spmkit.core.models import ForceCurve, ForceSegment

    contours = [70e-9, 95e-9, 120e-9]
    sep, f = _sawtooth_varying(contours, noise_frac=0.01, seed=0)
    seg = ForceSegment(
        segment_type="retract",
        direction="retract",
        raw_height=sep,
        raw_deflection=np.zeros_like(sep),
        force=f,
        separation=sep,
        state="force_n",
    )
    curve = ForceCurve(segments=(seg,))
    results = chain.analyze_retract(curve, model="wlc")
    assert len(results) == 3
    got = sorted(r.fit.contour_length for r in results)
    for recovered, want in zip(got, contours, strict=True):
        assert abs(recovered - want) / want < 0.06


def test_analyze_retract_sin_retract_da_error() -> None:
    """Una curva sin segmento de retracción falla con un error controlado."""
    from spmkit.core.analysis import chain
    from spmkit.core.models import ForceCurve, ForceSegment

    sep = np.linspace(6e-7, 0.0, 100)
    seg = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=sep,
        raw_deflection=np.zeros_like(sep),
        force=np.zeros_like(sep),
        separation=sep,
        state="force_n",
    )
    with pytest.raises(ValueError, match="retracci"):
        chain.analyze_retract(ForceCurve(segments=(seg,)))
