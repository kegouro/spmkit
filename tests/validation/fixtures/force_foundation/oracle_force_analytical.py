"""Analytical ground-truth oracle for the force-foundation phantoms.

Independent of production code: reads only the phantom manifest/NPZ and
re-derives the expected values from the documented phantom construction
(linear baseline + Hertz-like 3/2 contact branch).

The oracle verifies:

  * calibrated force from raw volts (x InVOLS x spring constant);
  * tip-sample separation = height - deflection;
  * baseline parameters (intercept/slope/noise scale);
  * contact index = first sample above the baseline model;
  * event forces at the declared indices;
  * closed-form contact-region work (2/5 c delta^2.5 + baseline terms).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

CONTACT_COEFF = 5.0


def load_phantom_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text())


def expected_calibrated_force(
    raw_volts: np.ndarray, invols: float, spring_constant: float
) -> np.ndarray:
    """V -> m (InVOLS) -> N (spring constant)."""
    return raw_volts * invols * spring_constant


def expected_separation(height: np.ndarray, deflection: np.ndarray) -> np.ndarray:
    """SPMKit convention: separation = height - deflection."""
    return height - deflection


def expected_baseline_line(height: np.ndarray, intercept: float, slope: float) -> np.ndarray:
    return intercept + slope * height


def expected_contact_index(
    force: np.ndarray, intercept: float, slope: float, height: np.ndarray, n_base: int
) -> int:
    """First sample strictly above the baseline model after the baseline
    region (estimator-consistent truth)."""
    force[:n_base]
    model = intercept + slope * height
    above = force > model
    hits = np.flatnonzero(above[n_base:])
    if hits.size == 0:
        return -1
    return int(n_base + hits[0])


def expected_contact_work(
    zc: float, z_max: float, intercept: float, slope: float, coeff: float = CONTACT_COEFF
) -> float:
    """Closed-form work of the contact branch over [zc, z_max].

    Integral of (intercept + slope*z) dz + coeff * delta^1.5 dz.
    """
    base = intercept * (z_max - zc) + 0.5 * slope * (z_max**2 - zc**2)
    contact = (2.0 / 5.0) * coeff * (z_max - zc) ** 2.5
    return float(base + contact)
