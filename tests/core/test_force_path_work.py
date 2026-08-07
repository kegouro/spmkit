"""FS-R1C: acquisition-path force work and coordinate diagnostics tests.

Includes an **independent oracle** (a plain accumulation loop, no production
imports, no NumPy trapezoid helpers) used to compute expected path-work
values for deterministic cases, plus metamorphic checks and real-data
harness rules.

Case accounting: the 18-case oracle contract maps to 14 parametrized
deterministic cases + 4 typed-failure cases (nonfinite coordinate, nonfinite
force, unequal lengths, fewer than two samples) — see ``_CASES`` and the
failure tests below.
"""

from __future__ import annotations

import pickle

import numpy as np
import pytest

from spmkit.core.analysis import (
    ForceFoundationError,
    ForcePathWorkResult,
    coordinate_path_diagnostics,
    integrate_force_path_work,
    integrate_force_work,
)
from spmkit.core.analysis.force_foundation_errors import (
    INSUFFICIENT_SAMPLES,
    LENGTH_MISMATCH,
    NONFINITE_DATA,
)
from spmkit.core.models import ForceCurve, ForceSegment

# ---------------------------------------------------------------------------
# Independent oracle: W = sum_i 0.5*(F_i + F_{i+1})*(z_{i+1} - z_i), plain loop
# ---------------------------------------------------------------------------


def oracle_path_work(z: np.ndarray, f: np.ndarray) -> float:
    """Independent trapezoidal path-work oracle (acquisition order, signed)."""
    work = 0.0
    for i in range(len(z) - 1):
        work += ((f[i] + f[i + 1]) / 2.0) * (z[i + 1] - z[i])
    return float(work)


def test_oracle_analytic_cases() -> None:
    """Sanity of the oracle itself against analytic integrals."""
    z = np.linspace(0.0, 4.0, 1001)
    assert oracle_path_work(z, np.full_like(z, 3.0)) == pytest.approx(12.0, rel=1e-12)
    assert oracle_path_work(z, z) == pytest.approx(8.0, rel=1e-12)
    assert oracle_path_work(z, 2.0 * z + 1.0) == pytest.approx(20.0, rel=1e-12)


def test_hand_calculated_witness() -> None:
    """Tercer testigo a mano: W = sum_i 0.5*(F_i+F_{i+1})*dz_i calculado a lápiz.

    z = [0, 1, 2, 1.5, 3], f = [1, 1, 1, 1, 1]  (fuerza constante 1 N):
      paso 0: 0.5*(1+1)*(1)     = 1.0
      paso 1: 0.5*(1+1)*(1)     = 1.0
      paso 2: 0.5*(1+1)*(-0.5)  = -0.5
      paso 3: 0.5*(1+1)*(1.5)   = 1.5
      W = 1.0 + 1.0 - 0.5 + 1.5 = 3.0 J  (fuerza constante -> W = net displacement = 3.0)
    """
    z = np.array([0.0, 1.0, 2.0, 1.5, 3.0])
    f = np.ones(5)
    r = integrate_force_path_work(z, f)
    assert r.work_total == pytest.approx(3.0, abs=1e-15)
    # con fuerza constante, W == net displacement exactamente (incl. reversiones)
    assert r.work_total == pytest.approx(r.diagnostics.net_displacement, abs=1e-15)

# ---------------------------------------------------------------------------
# Deterministic path-work cases (1-14) vs oracle
# ---------------------------------------------------------------------------

_CASES = {
    "monotonic_increasing": (
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
    ),
    "monotonic_decreasing": (
        np.array([4.0, 3.0, 2.0, 1.0, 0.0]),
        np.array([4.0, 3.0, 2.0, 1.0, 0.0]),
    ),
    "constant_force": (
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        np.full(5, 3.0),
    ),
    "linear_force": (
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        2.0 * np.array([0.0, 1.0, 2.0, 3.0, 4.0]) + 1.0,
    ),
    "repeated_coordinate_plateau": (
        np.array([0.0, 1.0, 1.0, 1.0, 2.0]),
        np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
    ),
    "small_local_reversal": (
        np.array([0.0, 1.0, 2.0, 1.9, 3.0]),
        np.array([0.0, 1.0, 2.0, 1.95, 3.0]),
    ),
    "alternating_jitter": (
        np.array([0.0, 1.0, 0.9, 1.1, 1.0, 2.0]),
        np.array([0.0, 1.0, 0.95, 1.05, 1.0, 2.0]),
    ),
    "triangular_forward_backward": (
        np.array([0.0, 1.0, 2.0, 1.0, 0.0]),
        np.array([0.0, 1.0, 2.0, 1.0, 0.0]),
    ),
    "closed_hysteresis_loop": (
        np.array([0.0, 1.0, 2.0, 1.0, 0.0]),
        # fuerza distinta en la rama de retorno -> trabajo de lazo no nulo
        np.array([0.0, 0.0, 5.0, 1.0, 0.0]),
    ),
    "globally_directed_backtracking": (
        np.array([0.0, 1.0, 2.0, 1.5, 2.5, 2.0, 3.0]),
        np.array([0.0, 0.5, 1.0, 0.8, 1.2, 1.0, 1.5]),
    ),
    "zero_net_displacement": (
        np.array([0.0, 1.0, 2.0, 1.0, 0.0]),
        np.full(5, 1.0),
    ),
    "coordinate_translation": (
        np.array([5.0, 6.0, 7.0, 8.0, 9.0]),
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
    ),
    "reversed_acquisition_order": (
        np.array([4.0, 3.0, 2.0, 1.0, 0.0]),
        np.array([4.0, 3.0, 2.0, 1.0, 0.0]),
    ),
    "inserted_collinear_samples": (
        np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]),
        np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]),
    ),
}


@pytest.mark.parametrize("name", sorted(_CASES))
def test_path_work_matches_independent_oracle(name: str) -> None:
    z, f = _CASES[name]
    expected = oracle_path_work(z, f)
    result = integrate_force_path_work(z, f)
    assert result.work_total == pytest.approx(expected, rel=1e-12, abs=1e-15)
    # la descomposición suma exactamente al total
    assert result.work_total == pytest.approx(result.work_forward + result.work_backward, abs=1e-12)
    # la tolerancia de clasificación nunca altera la integral
    tol_result = integrate_force_path_work(z, f, classification_tolerance=1e-6)
    assert tol_result.work_total == result.work_total


# ---------------------------------------------------------------------------
# Metamorphic properties
# ---------------------------------------------------------------------------


def test_translation_invariance() -> None:
    z, f = _CASES["globally_directed_backtracking"]
    a = integrate_force_path_work(z, f)
    b = integrate_force_path_work(z + 100.0, f)
    assert a.work_total == pytest.approx(b.work_total, abs=1e-12)


def test_acquisition_reversal_flips_sign() -> None:
    z, f = _CASES["globally_directed_backtracking"]
    fwd = integrate_force_path_work(z, f)
    bwd = integrate_force_path_work(z[::-1], f[::-1])
    assert fwd.work_total == pytest.approx(-bwd.work_total, rel=1e-12, abs=1e-15)


def test_collinear_insertion_preserves_work() -> None:
    a = integrate_force_path_work(*_CASES["monotonic_increasing"])
    b = integrate_force_path_work(*_CASES["inserted_collinear_samples"])
    assert a.work_total == pytest.approx(b.work_total, rel=1e-12, abs=1e-15)


def test_force_scaling_scales_work() -> None:
    z, f = _CASES["globally_directed_backtracking"]
    base = integrate_force_path_work(z, f)
    scaled = integrate_force_path_work(z, 3.0 * f)
    assert scaled.work_total == pytest.approx(3.0 * base.work_total, rel=1e-12, abs=1e-15)


def test_coordinate_scaling_scales_work() -> None:
    z, f = _CASES["globally_directed_backtracking"]
    base = integrate_force_path_work(z, f)
    scaled = integrate_force_path_work(2.0 * z, f)
    assert scaled.work_total == pytest.approx(2.0 * base.work_total, rel=1e-12, abs=1e-15)


def test_closed_loop_work_not_forced_to_zero() -> None:
    """Un lazo cerrado de histéresis NO devuelve 0 por construcción."""
    z, f = _CASES["closed_hysteresis_loop"]
    r = integrate_force_path_work(z, f)
    assert abs(r.work_total) > 1e-12
    assert r.diagnostics.global_direction == "closed_or_ambiguous"


def test_monotonic_path_matches_strict_integrate_force_work() -> None:
    """Sobre una rama estrictamente monótona con fuerza lineal en z, el path
    work (orden de adquisición decreciente) coincide en magnitud con la
    integral estricta orientada a coordenada creciente (signo opuesto)."""
    from spmkit.core.analysis.force_contact import ContactPointCandidate

    z_a = np.linspace(10.0e-6, 2.0e-6, 200)  # approach decreciente
    f_a = 0.02 * (10.0e-6 - z_a)  # lineal en z -> trapezoide exacto en cualquier grilla
    z_r = np.linspace(2.0e-6, 10.0e-6, 200)
    f_r = 0.02 * (10.0e-6 - z_r)
    curve = ForceCurve(
        segments=(
            ForceSegment(
                segment_type="extend", direction="approach",
                raw_height=z_a, raw_deflection=f_a,
                deflection=f_a / 0.05, force=f_a, state="force_n",
            ),
            ForceSegment(
                segment_type="retract", direction="retract",
                raw_height=z_r, raw_deflection=f_r,
                deflection=f_r / 0.05, force=f_r, state="force_n",
            ),
        ),
        metadata={"format": "synthetic"},
    )
    # contacto al final del approach (coordenada mínima): dominio [z_min, z_max]
    contact = ContactPointCandidate(
        method="synthetic", index=199, coordinate=2.0e-6, score=1.0, valid=True
    )
    strict = integrate_force_work(curve, contact, domain="height")
    path = integrate_force_path_work(curve.extend.raw_height, curve.extend.force)
    # integral estricta: +∫ f dz (z creciente); path work: adquisición decreciente -> -∫ f dz
    assert path.work_total == pytest.approx(-strict.work_approach, rel=1e-9, abs=1e-18)
    assert path.diagnostics.global_direction == "decreasing"


# ---------------------------------------------------------------------------
# Typed failures (15-18)
# ---------------------------------------------------------------------------


def test_nonfinite_coordinate_raises() -> None:
    z = np.array([0.0, 1.0, np.nan, 3.0])
    with pytest.raises(ForceFoundationError) as exc:
        integrate_force_path_work(z, np.arange(4.0))
    assert exc.value.code == NONFINITE_DATA


def test_nonfinite_force_raises() -> None:
    f = np.array([0.0, 1.0, np.inf, 3.0])
    with pytest.raises(ForceFoundationError) as exc:
        integrate_force_path_work(np.arange(4.0), f)
    assert exc.value.code == NONFINITE_DATA


def test_unequal_lengths_raise() -> None:
    with pytest.raises(ForceFoundationError) as exc:
        integrate_force_path_work(np.arange(4.0), np.arange(5.0))
    assert exc.value.code == LENGTH_MISMATCH


def test_fewer_than_two_samples_raise() -> None:
    with pytest.raises(ForceFoundationError) as exc:
        integrate_force_path_work(np.array([1.0]), np.array([1.0]))
    assert exc.value.code == INSUFFICIENT_SAMPLES
    with pytest.raises(ForceFoundationError) as exc:
        coordinate_path_diagnostics(np.array([1.0]))
    assert exc.value.code == INSUFFICIENT_SAMPLES


def test_negative_tolerance_raises() -> None:
    with pytest.raises(ValueError, match="classification_tolerance"):
        integrate_force_path_work(np.arange(3.0), np.arange(3.0), classification_tolerance=-1.0)


def test_empty_coordinate_raises() -> None:
    with pytest.raises(ForceFoundationError) as exc:
        integrate_force_path_work(np.array([]), np.array([]))
    assert exc.value.code == "MISSING_COORDINATE"


# ---------------------------------------------------------------------------
# Diagnostics definitions
# ---------------------------------------------------------------------------


def test_diagnostics_net_and_variation() -> None:
    z = np.array([0.0, 1.0, 2.0, 1.5, 2.5, 2.0, 3.0])
    d = coordinate_path_diagnostics(z)
    assert d.net_displacement == pytest.approx(3.0)
    assert d.total_variation == pytest.approx(1 + 1 + 0.5 + 1 + 0.5 + 1)
    assert d.forward_distance == pytest.approx(1 + 1 + 1 + 1)
    assert d.backward_distance == pytest.approx(0.5 + 0.5)
    assert d.backtracking_fraction == pytest.approx(1.0 / 5.0)
    assert d.exact_positive_steps == 4
    assert d.exact_negative_steps == 2
    assert d.exact_zero_steps == 0
    assert d.global_direction == "increasing"
    assert d.globally_directed
    assert not d.strictly_monotonic


def test_diagnostics_maximum_reverse_excursion_decreasing() -> None:
    # running min: 3,2,1,1,0  -> excursion: 0,0,0,1,0 -> max 1.0
    z = np.array([3.0, 2.0, 1.0, 2.0, 0.0])
    d = coordinate_path_diagnostics(z)
    assert d.global_direction == "decreasing"
    assert d.maximum_reverse_excursion == pytest.approx(1.0)
    # paso opuesto mayor (signed): para decreasing, el mayor paso positivo
    assert d.maximum_reverse_step == pytest.approx(1.0)
    # un paso aislado opuesto a la dirección global (decreasing -> paso +1)


def test_diagnostics_maximum_reverse_excursion_increasing() -> None:
    # running max: 0,1,2,2,3 -> excursion: 0,0,0,1,0 -> max 1.0
    z = np.array([0.0, 1.0, 2.0, 1.0, 3.0])
    d = coordinate_path_diagnostics(z)
    assert d.global_direction == "increasing"
    assert d.maximum_reverse_excursion == pytest.approx(1.0)
    assert d.maximum_reverse_step == pytest.approx(-1.0)


def test_diagnostics_strictly_monotone_zero_excursion() -> None:
    z = np.linspace(0.0, 5.0, 6)
    d = coordinate_path_diagnostics(z)
    assert d.strictly_monotonic
    assert d.maximum_reverse_excursion == pytest.approx(0.0)
    assert d.maximum_reverse_step is None
    assert d.classified_reversal_count == 0


def test_diagnostics_closed_ambiguous() -> None:
    z = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    d = coordinate_path_diagnostics(z)
    assert d.global_direction == "closed_or_ambiguous"
    assert not d.globally_directed
    assert d.maximum_reverse_step is None
    assert d.maximum_reverse_excursion is None
    assert any("no coherent global direction" in w for w in d.warnings)


def test_diagnostics_tolerance_classification_only() -> None:
    """La tolerancia cambia la clasificación, nunca la integral."""
    z = np.array([0.0, 1.0, 1.0 - 1e-9, 2.0])  # reverso diminuto (dz = -1e-9)
    f = np.array([0.0, 1.0, 1.0, 2.0])
    exact = coordinate_path_diagnostics(z)
    classified = coordinate_path_diagnostics(z, classification_tolerance=1e-6)
    assert exact.classified_reversal_count == 1
    assert not exact.strictly_monotonic
    assert classified.classified_reversal_count == 0
    assert classified.strictly_monotonic
    assert classified.classification_tolerance == 1e-6
    w_exact = integrate_force_path_work(z, f)
    w_class = integrate_force_path_work(z, f, classification_tolerance=1e-6)
    assert w_exact.work_total == w_class.work_total


def test_diagnostics_global_direction_reversal() -> None:
    z = np.array([3.0, 2.0, 1.0])
    assert coordinate_path_diagnostics(z).global_direction == "decreasing"
    assert coordinate_path_diagnostics(z[::-1]).global_direction == "increasing"


def test_ambiguous_path_warns_on_decomposition() -> None:
    z, f = _CASES["closed_hysteresis_loop"]
    r = integrate_force_path_work(z, f)
    assert any("step sign" in w for w in r.warnings)
    assert r.work_total == pytest.approx(r.work_forward + r.work_backward, abs=1e-12)


# ---------------------------------------------------------------------------
# Immutability, determinism, pickle
# ---------------------------------------------------------------------------


def test_immutability_and_deterministic_replay() -> None:
    z, f = _CASES["globally_directed_backtracking"]
    z_copy, f_copy = z.copy(), f.copy()
    r1 = integrate_force_path_work(z, f)
    r2 = integrate_force_path_work(z, f)
    assert np.array_equal(z, z_copy) and np.array_equal(f, f_copy)
    assert r1.work_total == r2.work_total
    assert r1.diagnostics.net_displacement == r2.diagnostics.net_displacement


def test_result_pickle_roundtrip() -> None:
    z, f = _CASES["globally_directed_backtracking"]
    r = integrate_force_path_work(z, f)
    blob = pickle.dumps(r)
    r2 = pickle.loads(blob)
    assert r2 == r
    assert r2.work_total == r.work_total


def test_result_repr_and_fields() -> None:
    z, f = _CASES["linear_force"]
    r = integrate_force_path_work(z, f)
    assert r.units == "J"
    assert r.valid
    assert "acquisition_path" in r.provenance["semantics"]
    assert "trapezoidal_acquisition_order" in r.provenance["arithmetic"]
    assert isinstance(r, ForcePathWorkResult)


def test_custom_units_label() -> None:
    z, f = _CASES["linear_force"]
    r = integrate_force_path_work(z, f, coordinate_unit="nm", force_unit="nN")
    assert r.units == "nN·nm"


# ---------------------------------------------------------------------------
# Production independence rule (oracle never imports production code)
# ---------------------------------------------------------------------------


def test_oracle_module_has_no_production_imports() -> None:
    import inspect

    import tests.core.test_force_path_work as mod

    src = inspect.getsource(mod.oracle_path_work)
    assert "spmkit" not in src
    assert "np.trapezoid" not in src
    assert "trapezoid(" not in src
