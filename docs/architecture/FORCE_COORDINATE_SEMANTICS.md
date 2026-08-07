# Force coordinate semantics: acquisition order vs coordinate order

**Scope**: how the SPMKit force stack treats a 1-D trajectory (a force-curve
segment) and why some operations integrate over an *ordered coordinate* while
others integrate over the *acquisition order*.

**Trigger (real data)**: the PAAm hydrogel JPK dataset
(`10.6084/m9.figshare.11637675.v3`, CC0).  Its tip-sample separation axis is
globally directed (net ≈ −8 µm per approach) but **not** strictly monotone:
56–74% of the per-step increments are negative at the nm scale (deflection
noise), with 76–84% backtracking fraction.  The strict work integration
(`integrate_force_work`) correctly rejects such an axis with
`NONMONOTONIC_COORDINATE` instead of fabricating a value.

## Acquisition order vs coordinate order

A segment is a *sequence of acquired samples* `(z_i, F_i)`, `i = 0..n-1`.
Two different mathematical objects can be built from it:

- **Coordinate-ordered representation**: the function `F(z)` over the
  travelled coordinate values.  Requires a single-valued branch (each `z`
  visited once per direction); local reversals make `F(z)` multivalued
  without a branch choice.
- **Acquisition-ordered path**: the trajectory `i -> (z_i, F_i)` with signed
  increments `dz_i = z_{i+1} - z_i`.

**Sorting is forbidden** as a silent repair: it reorders physics (the
force at a revisited coordinate belongs to a different acquisition time,
often a different contact state) and it hides the jitter that the user must
see.  A *documented, explicit* reorder for a specific algorithm (e.g. the
SMFS pull-order search) is a deliberate design, not a hidden repair.

## Path work vs monotonic-coordinate integral

**Monotonic-coordinate integral** (`integrate_force_work`, unchanged, strict):
two-segment (approach + retract), contact-limited common overlap domain,
monotone interpolation onto a grid, trapezoidal arithmetic.  Requires a
strictly (tolerance-classified) monotone axis; raises
`NONMONOTONIC_COORDINATE` otherwise.

**Acquisition-path work** (`integrate_force_path_work`, new):

    W = sum_i 0.5 * (F_i + F_{i+1}) * (z_{i+1} - z_i)

evaluated in sample-acquisition order with deterministic float64
accumulation.  Properties: signed `dz` retained; local reversals and closed
loops contribute their signed path work; repeated coordinates contribute
zero; coordinate translation leaves `W` unchanged; reversing acquisition
flips the sign; no monotonicity repair.  A local reversal is **not
automatically invalid** — it is part of the acquired trajectory.

## Operation classification

| Operation | Coordinate consumed | Category |
|---|---|---|
| `integrate_force_work` (strict work) | separation/height, both segments | C — STRICTLY_MONOTONIC_REQUIRED (inverts/interpolates) |
| `integrate_force_path_work` (new) | single segment, acquisition order | A — PATH_ORDER_SAFE (signed path integral) |
| `coordinate_path_diagnostics` (new) | single segment | A — classification only, never alters integrals |
| `extract_force_events` | separation/height windows | A — ordered samples + value windows |
| `compute_tip_sample_separation` | elementwise height − deflection | A |
| contact-point methods (threshold/ROV/piecewise) | height/force samples | A — ordered samples, no inversion |
| baseline fit / correction | sample-index based | A |
| `dissipation_energy` (legacy forcecurve) | given-order trapezoid | A — already path-ordered |
| SMFS `_pull_order` search | separation | C — explicit documented coordinate reorder |
| `contact_mechanics` interp | monotone branch | C — inversion by construction |
| `validate_time_axis` (viscoelastic) | time | C — strictly increasing time (separate domain) |
| `_pspline` parameterization | fit parameter | C |

No operation outside the path-work pair was changed by FS-R1C.

## Diagnostics and tolerance

`CoordinatePathDiagnostics` classifies without touching any integral:

- `global_direction` derives from the **net displacement** sign
  (`z[-1] - z[0]`); near-zero net → `closed_or_ambiguous`, never a forced
  approach/retract label.
- `backtracking_fraction` = backward distance / total variation.
- `maximum_reverse_excursion` is a *path-level* cumulative excursion from
  the running directional extremum (not a single-step statistic).
- `classification_tolerance` (default exactly 0.0, SI units) only affects
  classification (direction, reversal counts, `strictly_monotonic`); it is
  stored in provenance and **never** changes the numerical integral.

## Real PAAm diagnostic summary

Ten external CC0 files, verified against the committed manifest: all ten
approaches are globally directed `decreasing` (net −7.0…−8.2 µm), with
backtracking fractions 0.76–0.84, maximum reverse steps 2–9 nm and maximum
reverse excursions 2–13 nm.  Acquisition-path work: −2.3…−2.5e-14 J
(documented as a path integral, **not** validated material energy).

## Non-claims

Local reversal is not proven to be only noise; path work is not automatically
adhesion energy; no energy-per-area result; no thermodynamic interpretation
without a process model; no physical validation; no automatic loop
correction; no smoothing or denoising; no guarantee for segments with
ambiguous global direction; no change to algorithms that require monotonic
inversion; no time-domain reconstruction; no universal real-curve policy.
