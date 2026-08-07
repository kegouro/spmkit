# Golden path: acquisition-path force work on a real JPK curve

**Dataset**: *Atomic force microscopy indentation data of stiff and compliant
polyacrylamide hydrogels* — DOI `10.6084/m9.figshare.11637675.v3`, licence
**CC0** (manifest:
`tests/validation/fixtures/jpk_forcescan2/paam_dataset_manifest.json`).

This example runs the full public pipeline on one representative real curve
(~30 lines): load, calibrate, separate, prepare, inspect coordinate-path
diagnostics and compute acquisition-path work with signed contributions.

## 1. Load, calibrate and separate

```python
from spmkit.core.io import load_force
from spmkit.core.analysis import (
    calibrate_force_curve,
    compute_tip_sample_separation,
    fit_force_baseline,
    correct_force_baseline,
    contact_point_ensemble,
    coordinate_path_diagnostics,
    integrate_force_path_work,
)

volume = load_force("PAAm_Stiff_ROI6_force-save-2019.10.25-11.18.07.055.jpk-force")
curve = volume.curve(0)
calibrated = calibrate_force_curve(curve).curve
sep = compute_tip_sample_separation(calibrated)
baseline = fit_force_baseline(sep, model="linear")
corrected = correct_force_baseline(sep, baseline, scope="all")
contact = contact_point_ensemble(
    sep, methods=("threshold", "ratio_of_variances", "piecewise"), bootstrap_samples=0
)
print(contact.method_agreement, "contact methods agree at", contact.selected.coordinate, "m")
```

## 2. Coordinate-path diagnostics (classification only)

```python
ext = sep.extend
diagnostics = coordinate_path_diagnostics(ext.separation)
print(diagnostics.net_displacement)        # -8.13e-06 m  (approach global)
print(diagnostics.total_variation)         #  1.29e-05 m
print(diagnostics.backtracking_fraction)   #  0.815  (jitter-dominated)
print(diagnostics.global_direction)        # 'decreasing'
print(diagnostics.strictly_monotonic)      # False  -> strict integration rejects this axis
print(diagnostics.maximum_reverse_excursion)  # 3.07e-09 m  (nm-scale, path-level)
```

## 3. Acquisition-path work (signed, acquisition order)

```python
work = integrate_force_path_work(
    ext.separation, ext.force,
    provenance={"file": "PAAm ... 11.18.07.055.jpk-force", "segment": "extend"},
)
print(work.work_total)          # -2.48e-14 J  (signed path integral)
print(work.work_forward)        # contribution of steps in the global direction
print(work.work_backward)       # contribution of steps opposite the global direction
print(work.work_total - (work.work_forward + work.work_backward))  # 0.0 (invariant)
print(work.units)               # 'J'  (N * m)
print(work.provenance["semantics"])   # 'acquisition_path'
```

`W = sum_i 0.5*(F_i + F_{i+1})*(z_{i+1} - z_i)` evaluated strictly in
sample-acquisition order: signed `dz`, local reversals retained, no sorting,
no `abs()`, no smoothing, no point deletion.  The classification tolerance
(if ever given) only affects diagnostics, never the integral.

## What this proves (and what it does not)

Proved: the real curve loads, calibrates, separates and prepares; the axis is
globally directed (decreasing, net ≈ −8 µm) but not strictly monotone (57%
negative increments, nm-scale reversals); acquisition-path work is computed
deterministically with an exact decomposition invariant.

Not claimed: validated material energy (the −2.5e-14 J is a path integral,
not a thermodynamic quantity), adhesion energy per area, modulus, time-domain
analysis, or any physical validation.  The strict monotonic-coordinate
integration (`integrate_force_work`) remains unchanged and still rejects this
axis with `NONMONOTONIC_COORDINATE`.
