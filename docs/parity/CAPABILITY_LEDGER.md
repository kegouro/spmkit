# SPMKit Capability Ledger

Stable scientific capabilities registered by the Operation Registry v1.

- schema_version: 1
- operations: 74

Source of truth: `src/spmkit/core/capabilities.json` (generated view; do not edit by hand).

## FORCE.BASELINE.CORRECT

- operation_id: `force.baseline.correct`
- public_name: `correct_force_baseline`
- public_import: `spmkit.core.analysis:correct_force_baseline`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Force baseline correction)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Subtract the fitted baseline (offset + slope over height) with scope all/baseline/approach; slope correction changes the data (documented).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N

- parameters:
  - `curve` (positional, required) — Force curve.
  - `baseline` (positional, required) — Fitted baseline.
  - `scope` (keyword_only, 'all' values=['all', 'baseline', 'approach']) — Correction scope.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

## FORCE.BASELINE.FIT

- operation_id: `force.baseline.fit`
- public_name: `fit_force_baseline`
- public_import: `spmkit.core.analysis:fit_force_baseline`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Force baseline fit)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Fit the pre-contact baseline (first 10% of approach): linear offset + slope via polyfit; optional deterministic Huber-IRLS robust fit; residual RMS and robust scale; BASELINE_TOO_SHORT for too few points.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N

- parameters:
  - `curve` (positional, required) — Force curve.
  - `region` (keyword_only, 'pre_contact' values=['pre_contact']) — Baseline region.
  - `model` (keyword_only, 'linear' values=['linear']) — Baseline model.
  - `robust` (keyword_only, False) — Robust IRLS fit.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

## FORCE.CALIBRATION.APPLY

- operation_id: `force.calibration.apply`
- public_name: `calibrate_force_curve`
- public_import: `spmkit.core.analysis:calibrate_force_curve`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Force calibration application)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: raw deflection voltage (V) -> deflection (m) via InVOLS (m/V) -> force (N) via spring constant (N/m); already-calibrated pass-through; double calibration rejected (INVALID_CALIBRATION); missing calibration raises MISSING_CALIBRATION.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N

- parameters:
  - `curve` (positional, required) — Force curve to calibrate.
  - `calibration` (keyword_only, required) — Explicit calibration.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

## FORCE.CONTACT.ENSEMBLE

- operation_id: `force.contact.ensemble`
- public_name: `contact_point_ensemble`
- public_import: `spmkit.core.analysis:contact_point_ensemble`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Contact point (ensemble))
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Combine threshold/ROV/piecewise; robust location = median of valid candidate indices; explicit disagreement and spread; deterministic bootstrap only when requested; CONTACT_METHOD_DISAGREEMENT when fewer than two methods agree.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `curve` (positional, required) — Force curve.
  - `methods` (keyword_only, ['threshold', 'ratio_of_variances', 'piecewise']) — Contact methods.
  - `bootstrap_samples` (keyword_only, 0) — Bootstrap samples.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

- known deviations:
  - method spread does not constitute an uncertainty guarantee
  - maturity downgraded at independent audit: NUMERICALLY_VERIFIED -> SOFTWARE_VERIFIED

## FORCE.CONTACT.PIECEWISE

- operation_id: `force.contact.piecewise`
- public_name: `contact_point_piecewise`
- public_import: `spmkit.core.analysis:contact_point_piecewise`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Contact point (piecewise))
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Value-continuous piecewise baseline/contact polynomial fit over the search grid; requires a genuine residual improvement over a single whole-curve polynomial (flat curves fail).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `curve` (positional, required) — Force curve.
  - `baseline_order` (keyword_only, 1) — Baseline order.
  - `contact_order` (keyword_only, 2) — Contact order.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

## FORCE.CONTACT.RATIO_OF_VARIANCES

- operation_id: `force.contact.ratio_of_variances`
- public_name: `contact_point_ratio_of_variances`
- public_import: `spmkit.core.analysis:contact_point_ratio_of_variances`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Contact point (ratio of variances))
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Gavara 2016 ratio-of-variances contact: argmax of variance-after / variance-before over the window grid; requires a genuine variance jump (ratio >= 2) and sufficient length.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `curve` (positional, required) — Force curve.
  - `window` (keyword_only, 20) — Variance window.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

## FORCE.CONTACT.THRESHOLD

- operation_id: `force.contact.threshold`
- public_name: `contact_point_threshold`
- public_import: `spmkit.core.analysis:contact_point_threshold`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: nanite 4.2.3 (Contact point (nanite deviation_from_baseline profile))
- evidence profile: `COMPILED_NANITE_4_2_3_EXTERNAL_REFERENCE_FROZEN_PROFILE`

- contract: Baseline-relative threshold contact: first crossing of mean + k*sigma with persistence 3; validated against the frozen nanite 4.2.3 deviation_from_baseline contact index on the shared noiseless cases.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `curve` (positional, required) — Force curve.
  - `threshold_sigma` (keyword_only, 5.0) — Threshold in sigma.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`
  - `tests/validation/fixtures/force_foundation/force_foundation_external.npz`

- known deviations:
  - production threshold agrees with nanite deviation_from_baseline on clean flat-baseline cases (0..2 samples) but diverges on sloped/noisy baselines (up to 13 samples across the 17-case persisted matrix); NOT cross-validated as equivalent
  - sloped noiseless baselines degrade threshold recovery (characterized)

## FORCE.EVENTS.EXTRACT

- operation_id: `force.events.extract`
- public_name: `extract_force_events`
- public_import: `spmkit.core.analysis:extract_force_events`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Force events (snap-in / pull-off))
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Snap-in = minimum force before contact on approach (baseline-relative below mean - 3*sigma); pull-off = minimum force after contact on retract; physical windows; no event when the relevant segment is absent (EVENT_NOT_FOUND).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N

- parameters:
  - `curve` (positional, required) — Force curve.
  - `contact` (positional, required) — Contact point result.
  - `snap_in_window` (keyword_only, None) — Snap-in window (coordinate).
  - `pull_off_window` (keyword_only, None) — Pull-off window (coordinate).

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

## FORCE.FIT_WINDOW.SELECT

- operation_id: `force.fit_window.select`
- public_name: `select_contact_fit_window`
- public_import: `spmkit.core.analysis:select_contact_fit_window`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Contact fit window selection)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Contiguous contact fit window from the contact index, optionally trimmed by min/max indentation and min/max force; fewer than min_points raises EMPTY_FIT_WINDOW / INSUFFICIENT_FIT_POINTS; included mask consistent with n_points; non-mutating.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `min_indentation` (keyword_only, None) — Lower indentation bound (m).
  - `max_indentation` (keyword_only, None) — Upper indentation bound (m).
  - `min_force` (keyword_only, None) — Lower force bound (N).
  - `max_force` (keyword_only, None) — Upper force bound (N).
  - `min_points` (keyword_only, 20) — Minimum window size.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.INDENTATION.COMPUTE

- operation_id: `force.indentation.compute`
- public_name: `compute_indentation`
- public_import: `spmkit.core.analysis:compute_indentation`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Indentation from separation and contact)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Indentation = approach separation minus the FS-F1 contact coordinate; zero at the contact and positive into the sample; pre-contact samples excluded by the valid mask; requires a fit-eligible prepared curve (CURVE_NOT_FIT_ELIGIBLE typed failure); NONFINITE_INPUT typed failure; units m; non-mutating.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.MODEL.COMPARE

- operation_id: `force.model.compare`
- public_name: `compare_contact_models`
- public_import: `spmkit.core.analysis:compare_contact_models`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (AICc model comparison)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Model-relative comparison over the identical data subset; AICc weights normalized to 1; recommended model is the AICc minimum unless the runner-up retains considerable support (Delta AICc < 4 -> ambiguous, no recommendation); no physical-truth claim; misspecified fits detected (cone data -> sneddon weight > 0.9); unknown model raises ValueError.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `window` (positional, required) — FitWindowResult.
  - `models` (keyword_only, ['hertz_sphere', 'sneddon_cone', 'flat_punch', 'dmt']) — Candidate models.
  - `tip_radius` (keyword_only, required) — Tip radius (m).
  - `half_angle` (keyword_only, 0.3490658503988659) — Cone half-angle (rad).
  - `punch_radius` (keyword_only, None) — Punch radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.MODEL.FIT_DMT

- operation_id: `force.model.fit_dmt`
- public_name: `fit_dmt`
- public_import: `spmkit.core.analysis:fit_dmt`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (DMT fit)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Two-parameter fit of E and F_adh over the window trimmed past the snap-in region; on snap-in phantoms E within 30% and F_adh within 1.5e-9 N (FS-F1 contact ensemble is unstable on snap-in curves, up to ~10 samples off); typed failures INVALID_RADIUS, INVALID_POISSON_RATIO, INVALID_ADHESION_PARAMETER, OPTIMIZATION_FAILED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `window` (positional, required) — FitWindowResult.
  - `tip_radius` (keyword_only, required) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E_initial` (keyword_only, 1000000000.0) — Optimizer start (Pa).
  - `F_adh_initial` (keyword_only, 1e-09) — Adhesion start (N).

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

- known deviations:
  - snap-in curves: FS-F1 contact ensemble unstable (up to ~10 samples off); dedicated snap-in contact detection is future work

## FORCE.MODEL.FIT_FLAT_PUNCH

- operation_id: `force.model.fit_flat_punch`
- public_name: `fit_flat_punch`
- public_import: `spmkit.core.analysis:fit_flat_punch`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Flat punch fit)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Linear-modulus least-squares fit of E with punch radius and poisson ratio fixed; E within 5% on clean phantoms; typed failures INVALID_RADIUS, INVALID_POISSON_RATIO, OPTIMIZATION_FAILED, NONFINITE_INPUT; same result contract as fit_hertz_sphere.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `window` (positional, required) — FitWindowResult.
  - `punch_radius` (keyword_only, required) — Punch radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E_initial` (keyword_only, 1000000000.0) — Optimizer start (Pa).

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.MODEL.FIT_HERTZ

- operation_id: `force.model.fit_hertz`
- public_name: `fit_hertz_sphere`
- public_import: `spmkit.core.analysis:fit_hertz_sphere`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Hertz sphere fit)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Nonlinear least-squares fit of E over the fit window with tip radius and poisson ratio fixed; E within 5% on clean phantoms (contact-precision limited); typed failures INVALID_RADIUS, INVALID_POISSON_RATIO, OPTIMIZATION_FAILED, NONFINITE_INPUT; result carries parameters, covariance, residuals, AIC/AICc/BIC, rmse and window provenance.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `window` (positional, required) — FitWindowResult.
  - `tip_radius` (keyword_only, required) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E_initial` (keyword_only, 1000000000.0) — Optimizer start (Pa).

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.MODEL.FIT_JKR

- operation_id: `force.model.fit_jkr`
- public_name: `fit_jkr`
- public_import: `spmkit.core.analysis:fit_jkr`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (JKR fit)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Two-parameter fit of E and w over the window trimmed past the snap-in region; loading curve parametrized by the contact radius (monotone for a >= a0, range derived from data); w=0 reduces to hertz; on snap-in phantoms E within 20% and w within 30%; typed failures INVALID_RADIUS, INVALID_POISSON_RATIO, INVALID_ADHESION_PARAMETER, OPTIMIZATION_FAILED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `window` (positional, required) — FitWindowResult.
  - `tip_radius` (keyword_only, required) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E_initial` (keyword_only, 1000000000.0) — Optimizer start (Pa).
  - `w_initial` (keyword_only, 0.001) — Work-of-adhesion start (J/m^2).

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

- known deviations:
  - snap-in curves: same contact-ensemble limitation as fit_dmt

## FORCE.MODEL.FIT_SNEDDON

- operation_id: `force.model.fit_sneddon`
- public_name: `fit_sneddon_cone`
- public_import: `spmkit.core.analysis:fit_sneddon_cone`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Sneddon cone fit)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Nonlinear least-squares fit of E with cone half-angle and poisson ratio fixed; E within 5% on clean phantoms; typed failures INVALID_ANGLE, INVALID_POISSON_RATIO, OPTIMIZATION_FAILED, NONFINITE_INPUT; same result contract as fit_hertz_sphere.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `indentation` (positional, required) — IndentationResult.
  - `window` (positional, required) — FitWindowResult.
  - `half_angle` (keyword_only, required) — Cone half-angle (rad).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E_initial` (keyword_only, 1000000000.0) — Optimizer start (Pa).

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.MODEL.FORWARD

- operation_id: `force.model.forward`
- public_name: `forward_model`
- public_import: `spmkit.core.analysis:forward_model`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Contact-model forward equations)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Frozen closed-form loading equations with reduced modulus E* = E/(1-nu^2): hertz F = (4/3) E* sqrt(R) d^1.5; sneddon F = (2 tan(alpha)/pi) E* d^2; flat punch F = 2 E* R d; dmt F = hertz - F_adh; jkr parametric contact-radius loading curve (monotone, derived range, w=0 reduces to hertz); SI units N; unknown model raises ValueError.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N

- parameters:
  - `model` (positional, required) — Model name.
  - `delta` (positional, required) — Indentation array (m).
  - `params` (positional, required) — Model parameters.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.PREPARE

- operation_id: `force.prepare`
- public_name: `prepare_force_curve`
- public_import: `spmkit.core.analysis:prepare_force_curve`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Force curve preparation pipeline)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Explicit orchestration over the 12 public primitives: segments -> calibration -> tip-sample separation -> baseline fit/correction -> contact ensemble -> events -> work -> quality; provenance names every decision; contact detection runs on the calibrated curve.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `curve` (positional, required) — Force curve.
  - `calibration` (keyword_only, None) — Explicit calibration.
  - `baseline_model` (keyword_only, 'linear' values=['linear']) — Baseline model.
  - `contact_methods` (keyword_only, ['threshold', 'ratio_of_variances', 'piecewise']) — Contact methods.
  - `bootstrap_samples` (keyword_only, 0) — Bootstrap samples.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

- known deviations:
  - orchestration maturity is bounded by its weakest material component (contact ensemble and quality score are SOFTWARE_VERIFIED heuristics)

## FORCE.QUALITY.SCORE

- operation_id: `force.quality.score`
- public_name: `score_force_curve_quality`
- public_import: `spmkit.core.analysis:score_force_curve_quality`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Force curve quality scoring)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Typed failure reasons (14 codes) beside a summary score; component diagnostics always explicit; eligibility for contact-model fitting.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `curve` (positional, required) — Force curve.
  - `segmentation` (keyword_only, None) — Segmentation result.
  - `baseline` (keyword_only, None) — Baseline result.
  - `contact` (keyword_only, None) — Contact result.
  - `events` (keyword_only, None) — Events result.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

- known deviations:
  - the aggregate summary score is a designed heuristic; it is not an externally validated scientific quality probability

## FORCE.RELIABILITY.BOOTSTRAP

- operation_id: `force.reliability.bootstrap`
- public_name: `bootstrap_force_fit`
- public_import: `spmkit.core.analysis:bootstrap_force_fit`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Residual bootstrap)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Deterministic residual (or block-residual) bootstrap of the hertz fit; percentile intervals and bias estimate over E; replicate failures counted, never masked; success fraction below min_success_fraction (or outside [0,1]) raises BOOTSTRAP_INSUFFICIENT_SUCCESS; same seed reproduces identical samples.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `spec` (positional, required) — (prepared, indentation, window, model) tuple.
  - `samples` (keyword_only, 500) — Replicate count.
  - `seed` (keyword_only, 0) — RNG seed.
  - `strategy` (keyword_only, 'residual' values=['residual', 'block_residual']) — Resampling strategy.
  - `tip_radius` (keyword_only, 1e-08) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `min_success_fraction` (keyword_only, 0.5) — Minimum success fraction.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.RELIABILITY.DIAGNOSE

- operation_id: `force.reliability.diagnose`
- public_name: `diagnose_force_fit`
- public_import: `spmkit.core.analysis:diagnose_force_fit`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Fit diagnostics policy)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Explicit diagnostics: residual RMS, autocorrelation and curvature proxies, covariance condition number and max parameter correlation, one-at-a-time contact/window sensitivity, bootstrap success fraction, model-ambiguity flag; the summary status is a policy (ok/review), never a probability; failure reasons listed explicitly.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `fit` (positional, required) — Fit result.
  - `sensitivity` (keyword_only, None) — Sensitivity result.
  - `bootstrap` (keyword_only, None) — Bootstrap result.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.RELIABILITY.SENSITIVITY

- operation_id: `force.reliability.sensitivity`
- public_name: `analyze_force_fit_sensitivity`
- public_import: `spmkit.core.analysis:analyze_force_fit_sensitivity`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Contact/window sensitivity multiverse)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Deterministic multiverse over contact offsets and fit-window lower-bound fractions (bounded at max_configurations=512); one-at-a-time contact and window sensitivity indices relative to the baseline configuration; E stability ranges and robust medians; dominant sensitivity classified as contact, window or none (relative index > 20%); failed configurations recorded, never dropped; CONTACT_SENSITIVITY_HIGH when no configuration succeeds.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `prepared` (positional, required) — Prepared curve.
  - `contact_offsets` (keyword_only, [-3, -1, 0, 1, 3]) — Contact offsets (samples).
  - `fit_window_variants` (keyword_only, [0.0, 0.05]) — Window lower-bound fractions.
  - `baseline_variants` (keyword_only, ['linear']) — Baseline models.
  - `models` (keyword_only, ['hertz_sphere']) — Models.
  - `max_configurations` (keyword_only, 512) — Multiverse bound.
  - `tip_radius` (keyword_only, 1e-08) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.SEGMENT.IDENTIFY

- operation_id: `force.segment.identify`
- public_name: `identify_force_segments`
- public_import: `spmkit.core.analysis:identify_force_segments`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Force segment identification)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Identify approach/retract sample indices of a ForceCurve; instrument labels trusted when both segments exist, else turning point = height extremum; no sample reordering.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `curve` (positional, required) — Force curve to segment.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

- known deviations:
  - single-segment inference may misplace the turning point on flat turning points

## FORCE.SEPARATION.TIP_SAMPLE

- operation_id: `force.separation.tip_sample`
- public_name: `compute_tip_sample_separation`
- public_import: `spmkit.core.analysis:compute_tip_sample_separation`
- family: FORCE
- maturity: CROSS_VALIDATED
- status: stable
- reference: nanite 4.2.3 (Tip-sample separation (nanite tip-position profile))
- evidence profile: `COMPILED_NANITE_4_2_3_EXTERNAL_REFERENCE_FROZEN_PROFILE`

- contract: Tip-sample separation = height - deflection per segment; no contact offset applied; validated against the frozen nanite 4.2.3 tip-position convention (tip = height + force/k + offset).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `curve` (positional, required) — Force curve.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`
  - `tests/validation/fixtures/force_foundation/force_foundation_external.npz`

- known deviations:
  - bitwise external identity not claimed; convention validated numerically on the frozen nanite profile

## FORCE.SMFS.BATCH

- operation_id: `force.smfs.batch`
- public_name: `analyze_smfs_batch`
- public_import: `spmkit.core.analysis:analyze_smfs_batch`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Deterministic batch orchestration over per-curve analyses: e)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Deterministic batch orchestration over per-curve analyses: every result retained, failed curves retained with reasons, unified event table with curve origins, population aggregation, stable ordering and replay; nothing silently dropped; the orchestration policy is SOFTWARE_VERIFIED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `analyses` (positional, required) — Per-curve analyses.
  - `group_by` (keyword_only, 'loading_rate_decade' values=['none', 'loading_rate_decade']) — Grouping policy.
  - `n_groups` (keyword_only, 4) — Number of groups.

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.CONTOUR_INCREMENT

- operation_id: `force.smfs.contour_increment`
- public_name: `infer_contour_length_increments`
- public_import: `spmkit.core.analysis:infer_contour_length_increments`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Delta contour length per event from independent pre/post WLC)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Delta contour length per event from independent pre/post WLC fits on the ABSOLUTE molecular extension (a section-relative fit would absorb the event offset into a biased contour); event-index sensitivity characterized by explicit shifts; within 10% on the doubling-contour phantoms.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `extension` (positional, required) — Extension result.
  - `events` (positional, required) — Quantified events.
  - `model` (keyword_only, 'worm_like_chain') — Polymer model.
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `pre_margin` (keyword_only, 2) — Pre-event margin (samples).
  - `post_margin` (keyword_only, 2) — Post-event margin (samples).
  - `min_points` (keyword_only, 8) — Minimum window points.
  - `sensitivity_shifts` (keyword_only, [0]) — Event-index shifts.

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.EVENTS.DETECT

- operation_id: `force.smfs.events.detect`
- public_name: `detect_unfolding_events`
- public_import: `spmkit.core.analysis:detect_unfolding_events`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Unfolding-event detection on the pull-ordered retract segment)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Unfolding-event detection on the pull-ordered retract section: sustained force drops with public thresholds (drop magnitude, persistence, minimum separation, boundary margin); rejected candidates retained with reasons; the final detachment is distinguished from internal unfolding; sub-threshold drops raise NO_EVENTS typed.  The detector is a documented heuristic (SOFTWARE_VERIFIED) evaluated with true/false positives on deterministic phantoms.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N

- parameters:
  - `extension` (positional, required) — Extension result.
  - `min_force_drop` (keyword_only, None) — Minimum drop (N).
  - `min_persistence` (keyword_only, 3) — Sustained-drop samples.
  - `min_event_separation` (keyword_only, 3) — Minimum separation (samples).
  - `noise_sigma` (keyword_only, None) — Noise scale (N).
  - `boundary_margin` (keyword_only, 2) — Boundary margin (samples).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.EVENTS.QUANTIFY

- operation_id: `force.smfs.events.quantify`
- public_name: `quantify_unfolding_events`
- public_import: `spmkit.core.analysis:quantify_unfolding_events`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Assign explicit pre/post windows and local loading rates to )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Assign explicit pre/post windows and local loading rates to every selected event; the pre window spans the polymer section between the previous event (or the tether zero) and the event; the post window spans the section to the next event (or the section end).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N / m

- parameters:
  - `extension` (positional, required) — Extension result.
  - `events` (positional, required) — Detected events.
  - `pre_margin` (keyword_only, 2) — Pre-event margin (samples).
  - `post_margin` (keyword_only, 2) — Post-event margin (samples).
  - `min_points` (keyword_only, 8) — Minimum window points.

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.EXTENSION.COMPUTE

- operation_id: `force.smfs.extension.compute`
- public_name: `compute_molecular_extension`
- public_import: `spmkit.core.analysis:compute_molecular_extension`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Molecular extension of the retract segment with an explicit t)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Molecular extension of the retract section with an explicit tether-zero policy: offset (physical m), index, pre_event (caller section start), or the estimator (retract zero-force crossing with its own diagnostics); the zero is never inferred silently from the contact; UNRESOLVED_TETHER_ZERO and INVALID_REFERENCE_POLICY typed; the estimator policy is a documented heuristic making the complete operation SOFTWARE_VERIFIED; the JPK/NID readers do not populate segment time (the SMFS retract section requires an explicit time axis where used).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `reference` (keyword_only, 'index' values=['offset', 'index', 'pre_event', 'estimator']) — Tether-zero reference policy.
  - `reference_value` (keyword_only, None) — Offset (m) or index.
  - `segment` (keyword_only, 'retract') — Segment (retract only).
  - `estimator_noise_sigma` (keyword_only, None) — Estimator noise scale.

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.FORCE_CLAMP.SURVIVAL

- operation_id: `force.smfs.force_clamp.survival`
- public_name: `estimate_force_clamp_survival`
- public_import: `spmkit.core.analysis:estimate_force_clamp_survival`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Kaplan-Meier survival with right censoring over explicit lif)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Kaplan-Meier survival with right censoring over explicit lifetimes and flags: events before censors at ties, events leave the risk set, censored observations never discarded; the median lifetime is typed UNDEFINED_MEDIAN when unreachable; the exponential rate is the censoring-aware MLE n_events/sum(times); matches the independent oracle exactly.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: s

- parameters:
  - `lifetimes` (positional, required) — Lifetimes (s).
  - `censored` (positional, required) — Censoring flags (0 event, 1 censored).
  - `force_level` (keyword_only, required) — Clamp force level (N).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `fit_exponential_rate` (keyword_only, True) — Fit the MLE rate.

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.KINETICS.BELL_EVANS

- operation_id: `force.smfs.kinetics.bell_evans`
- public_name: `fit_bell_evans`
- public_import: `spmkit.core.analysis:fit_bell_evans`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Bell-Evans fit over (loading rate, rupture force) series: th)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Bell-Evans fit over (loading rate, rupture force) series: the primary estimator is the frozen most-probable-force regression F* = (k_B T/x_beta) ln(r x_beta/(k0 k_B T)) with the survival convention S(F) = exp(-k0 k_B T/(r x_beta)(exp(F x_beta/k_B T) - 1)); a bounded likelihood runs as a secondary with an identifiability diagnosis (the BE likelihood is degenerate toward x_beta -> 0, documented); narrow-rate ranges carry an IDENTIFIABILITY_LIMITED warning; x_beta recovered within 10% on the phantoms.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m / 1/s

- parameters:
  - `loading_rates` (positional, required) — Loading rates (N/s).
  - `rupture_forces` (positional, required) — Rupture forces (N).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `k0_initial` (keyword_only, 1.0) — Zero-force rate start (1/s).
  - `x_beta_initial` (keyword_only, 1e-09) — Transition distance start (m).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.KINETICS.DHS

- operation_id: `force.smfs.kinetics.dhs`
- public_name: `fit_dudko_hummer_szabo`
- public_import: `spmkit.core.analysis:fit_dudko_hummer_szabo`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Dudko-Hummer-Szabo likelihood fit (k0, x_beta, dG) with the )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Dudko-Hummer-Szabo likelihood fit (k0, x_beta, dG) with the frozen shape convention nu in {1/2, 2/3}, log-space evaluation with a consistent rate cap, the domain 1 - nu F x_beta/dG > 0 enforced; the Bell limit nu -> 0 recovers the BE rate; the fitted energy landscape is not claimed to be physically unique; parameters recovered within the documented wide bounds with the response reconstruction verified.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m / 1/s / J

- parameters:
  - `loading_rates` (positional, required) — Loading rates (N/s).
  - `rupture_forces` (positional, required) — Rupture forces (N).
  - `nu` (keyword_only, 0.6666666666666666) — Potential shape (1/2 cusp, 2/3 linear-cubic).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `k0_initial` (keyword_only, 1.0) — Zero-force rate start (1/s).
  - `x_beta_initial` (keyword_only, 1e-09) — Transition distance start (m).
  - `dg_initial` (keyword_only, 1e-19) — Barrier height start (J).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.LOADING_RATE

- operation_id: `force.smfs.loading_rate`
- public_name: `compute_event_loading_rates`
- public_import: `spmkit.core.analysis:compute_event_loading_rates`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Local loading rate per event: the least-squares slope of for)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Local loading rate per event: the least-squares slope of force vs time over the pre-event window plus the robust median-of-pairs slope (N/s); the theoretical rate (effective stiffness x pulling velocity) is reported separately when both are supplied, never substituted; requires an explicit time axis.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: N/s

- parameters:
  - `extension` (positional, required) — Extension result.
  - `events` (positional, required) — Quantified events.
  - `window_samples` (keyword_only, 10) — Pre-event window (samples).
  - `min_samples` (keyword_only, 3) — Minimum samples.
  - `pulling_velocity` (keyword_only, None) — Pulling velocity (m/s).
  - `effective_stiffness` (keyword_only, None) — Stiffness (N/m).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.MODEL.COMPARE

- operation_id: `force.smfs.model.compare`
- public_name: `compare_polymer_models`
- public_import: `spmkit.core.analysis:compare_polymer_models`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (AICc comparison of the polymer models over the identical obs)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: AICc comparison of the polymer models over the identical observation set with relative weights only; Delta AICc < 4 ambiguity; failed models retained as warnings; no molecular-truth claim; the recommendation policy is SOFTWARE_VERIFIED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `extension` (positional, required) — Molecular extension (m).
  - `force` (positional, required) — Retract force (N).
  - `models` (keyword_only, ['worm_like_chain', 'extensible_worm_like_chain', 'freely_jointed_chain', 'extensible_freely_jointed_chain']) — Candidate models.
  - `temperature` (keyword_only, 298.0) — Temperature (K).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.MODEL.EXTENSIBLE_FJC

- operation_id: `force.smfs.model.extensible_fjc`
- public_name: `fit_extensible_freely_jointed_chain`
- public_import: `spmkit.core.analysis:fit_extensible_freely_jointed_chain`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Extensible FJC fit (Lc, b, Sk) in the extension space x/Lc =)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Extensible FJC fit (Lc, b, Sk) in the extension space x/Lc = L(y) + F/Sk with Sk the segment stretch force (N); Sk -> inf reduces to the FJC; Lc/b within 2%/5% on clean phantoms; the stretch scale is weakly identifiable from a single section (documented).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `extension` (positional, required) — Molecular extension (m).
  - `force` (positional, required) — Retract force (N).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `Lc_initial` (keyword_only, None) — Contour start (m).
  - `b_initial` (keyword_only, None) — Kuhn length start (m).
  - `Sk_initial` (keyword_only, None) — Stretch force start (N).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.MODEL.EXTENSIBLE_WLC

- operation_id: `force.smfs.model.extensible_wlc`
- public_name: `fit_extensible_worm_like_chain`
- public_import: `spmkit.core.analysis:fit_extensible_worm_like_chain`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Implicit extensible WLC fit (Lc, Lp, S) with the Odijk-style)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Implicit extensible WLC fit (Lc, Lp, S) with the Odijk-style convention F = (k_BT/Lp)[1/(4(1-x/Lc+F/S)^2) - 1/4 + x/Lc - F/S], solved per point by brentq with a force-scale xtol; S -> inf reduces to the WLC; Lc within 5% and Lp within 20% on clean phantoms; the stretch modulus is weakly identifiable from a single section (documented).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `extension` (positional, required) — Molecular extension (m).
  - `force` (positional, required) — Retract force (N).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `Lc_initial` (keyword_only, None) — Contour start (m).
  - `Lp_initial` (keyword_only, None) — Persistence start (m).
  - `S_initial` (keyword_only, None) — Stretch modulus start (N).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.MODEL.FJC

- operation_id: `force.smfs.model.fjc`
- public_name: `fit_freely_jointed_chain`
- public_import: `spmkit.core.analysis:fit_freely_jointed_chain`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (FJC fit (Lc, b) in the extension space x/Lc = coth(y) - 1/y )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: FJC fit (Lc, b) in the extension space x/Lc = coth(y) - 1/y with y = F b/k_BT (stable Langevin), separable closed-form Lc per candidate b; Lc/b within 2%/5% on clean phantoms; the persistence length is reported as Lp = b/2.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `extension` (positional, required) — Molecular extension (m).
  - `force` (positional, required) — Retract force (N).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `Lc_initial` (keyword_only, None) — Contour start (m).
  - `b_initial` (keyword_only, None) — Kuhn length start (m).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.MODEL.WLC

- operation_id: `force.smfs.model.wlc`
- public_name: `fit_worm_like_chain`
- public_import: `spmkit.core.analysis:fit_worm_like_chain`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (WLC fit (Lc, Lp) by the Marko-Siggia loading relation F = (k)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: WLC fit (Lc, Lp) by the Marko-Siggia loading relation F = (k_BT/Lp)[1/(4(1-x/Lc)^2) - 1/4 + x/Lc] with a separable closed-form Lp per candidate Lc (deterministic 1-D search); Lc/Lp within 2%/5% on clean phantoms; the singular domain (x >= Lc) is typed POLYMER_SINGULARITY.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m

- parameters:
  - `extension` (positional, required) — Molecular extension (m).
  - `force` (positional, required) — Retract force (N).
  - `temperature` (keyword_only, 298.0) — Temperature (K).
  - `Lc_initial` (keyword_only, None) — Contour start (m).
  - `Lp_initial` (keyword_only, None) — Persistence start (m).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.POPULATION

- operation_id: `force.smfs.population`
- public_name: `analyze_smfs_event_population`
- public_import: `spmkit.core.analysis:analyze_smfs_event_population`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Aggregate event records into a population: rupture-force, co)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Aggregate event records into a population: rupture-force, contour-increment and loading-rate summaries; deterministic grouping (none or loading_rate_decade) with raw assignments exposed; ambiguity retained for small populations; no molecular-identity claim; the grouping policy is SOFTWARE_VERIFIED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `event_records` (positional, required) — Event records.
  - `group_by` (keyword_only, 'loading_rate_decade' values=['none', 'loading_rate_decade']) — Grouping policy.
  - `n_groups` (keyword_only, 4) — Number of groups.
  - `force_levels` (keyword_only, None) — Force levels (N).

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.SMFS.WINDOW.SELECT

- operation_id: `force.smfs.window.select`
- public_name: `select_smfs_fit_windows`
- public_import: `spmkit.core.analysis:select_smfs_fit_windows`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Explicit polymer fit window on the molecular extension axis:)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Explicit polymer fit window on the molecular extension axis: negative extensions always excluded (the polymer domain starts at the tether zero), extension/force bounds, minimum points; EMPTY_WINDOW and INSUFFICIENT_POINTS typed; the window policy is SOFTWARE_VERIFIED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m / N

- parameters:
  - `extension` (positional, required) — Molecular extension (m).
  - `force` (positional, required) — Retract force (N).
  - `min_extension` (keyword_only, None) — Lower extension bound (m).
  - `max_extension` (keyword_only, None) — Upper extension bound (m).
  - `min_force` (keyword_only, None) — Lower force bound (N).
  - `max_force` (keyword_only, None) — Upper force bound (N).
  - `min_points` (keyword_only, 10) — Minimum window size.
  - `window_label` (keyword_only, None) — Window identifier.

- evidence:
  - `tests/validation/fixtures/force_smfs/smfs_reference.json`
  - `tests/validation/fixtures/force_smfs/smfs_reference.npz`
  - `tests/validation/test_force_smfs_validation.py`
  - `tests/core/test_force_smfs.py`

## FORCE.VISCO.CONTACT.LEE_RADOK

- operation_id: `force.visco.contact.lee_radok`
- public_name: `fit_lee_radok_sphere`
- public_import: `spmkit.core.analysis:fit_lee_radok_sphere`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Fits the SLS relaxation modulus through the Lee-Radok spheri)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Fits the SLS relaxation modulus through the Lee-Radok spherical hereditary integral on the monotonic loading region: F(t) = c int_0^t E(t - t') d/dt' delta(t')^1.5 dt'; the contact radius must not decrease (LEE_RADOK_NONMONOTONIC typed); loading-only validity; the loading history is trimmed to the contact (indentation >= 0, documented); recovery within ~40% E0/E_inf and ~50% tau on clean phantoms (the loading curve carries less information than a hold).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `protocol` (positional, required) — Protocol result.
  - `tip_radius` (keyword_only, required) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E0_initial` (keyword_only, 1000000.0) — Modulus start (Pa).
  - `E_inf_initial` (keyword_only, 500000.0) — Equilibrium modulus start (Pa).
  - `tau_initial` (keyword_only, 1.0) — Relaxation time start (s).

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.CONTACT.TING

- operation_id: `force.visco.contact.ting`
- public_name: `fit_ting_sphere`
- public_import: `spmkit.core.analysis:fit_ting_sphere`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Fits the SLS relaxation modulus through the Ting spherical i)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Fits the SLS relaxation modulus through the Ting spherical integral with contact-time memory: loading = Lee-Radok; unloading F(t) = c int_0^{t1(t)} E(t - t') d/dt' delta(t')^1.5 dt' with delta(t1(t)) = delta(t) on the monotone loading portion; the loading history is trimmed to the contact and the unloading history truncated at the contact (documented); TING_HISTORY_UNAVAILABLE typed when the history cannot be reconstructed; the production quadrature is the first-order increment rule (parity with the substep oracle 0.5%).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `protocol` (positional, required) — Protocol result.
  - `tip_radius` (keyword_only, required) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `E0_initial` (keyword_only, 1000000.0) — Modulus start (Pa).
  - `E_inf_initial` (keyword_only, 500000.0) — Equilibrium modulus start (Pa).
  - `tau_initial` (keyword_only, 1.0) — Relaxation time start (s).

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.CREEP.EXTRACT

- operation_id: `force.visco.creep.extract`
- public_name: `extract_creep_compliance`
- public_import: `spmkit.core.analysis:extract_creep_compliance`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Extracts the creep compliance increment of a force hold: (in)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Extracts the creep compliance increment of a force hold: (indentation(t) - indentation(0))/F_hold on the relative hold time; the increment is robust to the contact-coordinate precision (the absolute level is carried in indentation_at_hold_start); missing hold raises EMPTY_REGION; zero held force raises INVALID_RESPONSE.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: s / N / m

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `protocol` (positional, required) — Protocol result.
  - `segment` (keyword_only, 'extend') — Segment name.
  - `hold_kind` (keyword_only, 'hold_force') — Hold region kind.
  - `hold_force_median` (keyword_only, True) — Median (vs mean) held force.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.MODEL.COMPARE

- operation_id: `force.visco.model.compare`
- public_name: `compare_viscoelastic_models`
- public_import: `spmkit.core.analysis:compare_viscoelastic_models`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Model-relative AICc comparison over identical observations w)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Model-relative AICc comparison over identical observations with the finite-sample correction; Delta AICc < 4 ambiguity; failed candidates retained as warnings; weights are relative support, never a probability of physical correctness; the recommendation policy is SOFTWARE_VERIFIED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `response` (positional, required) — Relaxation or creep response.
  - `models` (keyword_only, None) — Candidate models.
  - `tip_radius` (keyword_only, None) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `n_terms` (keyword_only, 2) — Prony terms for the generalized Maxwell.
  - `t_ref` (keyword_only, None) — Reference time for the power law.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.MODEL.GENERALIZED_MAXWELL

- operation_id: `force.visco.model.generalized_maxwell`
- public_name: `fit_generalized_maxwell`
- public_import: `spmkit.core.analysis:fit_generalized_maxwell`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Prony normalized relaxation fit n(t) = 1 - sum(alpha) + sum()
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Prony normalized relaxation fit n(t) = 1 - sum(alpha) + sum(alpha_i exp(-t/tau_i)) with alpha_i >= 0, sum(alpha) <= 1, tau_i > 0, deterministic ordering by ascending tau; duplicate relaxation times are rejected typed (PRONY_DUPLICATE_TAU); no claim that the recovered spectrum is unique; nearly equal time constants carry a bounded-identifiability warning.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: s

- parameters:
  - `response` (positional, required) — Relaxation response.
  - `n_terms` (keyword_only, 2 bounds=[1, 8]) — Number of Prony terms.
  - `tip_radius` (keyword_only, None) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.MODEL.KELVIN_VOIGT

- operation_id: `force.visco.model.kelvin_voigt`
- public_name: `fit_kelvin_voigt`
- public_import: `spmkit.core.analysis:fit_kelvin_voigt`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Kelvin-Voigt creep fit J(t) = (1/E)(1 - exp(-t/tau)), tau = )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Kelvin-Voigt creep fit J(t) = (1/E)(1 - exp(-t/tau)), tau = eta/E (retardation time); requires a CreepResponseResult (PROTOCOL_MODEL_MISMATCH typed otherwise); deterministic multi-start least squares; E within 10% and tau within 10% on clean phantoms; the model cannot represent instantaneous stress relaxation (documented).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `response` (positional, required) — Creep response.
  - `E_initial` (keyword_only, None) — Modulus start (Pa).
  - `tau_initial` (keyword_only, None) — Retardation time start (s).

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.MODEL.MAXWELL

- operation_id: `force.visco.model.maxwell`
- public_name: `fit_maxwell`
- public_import: `spmkit.core.analysis:fit_maxwell`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Maxwell relaxation fit n(t) = exp(-t/tau), tau = eta/E; the )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Maxwell relaxation fit n(t) = exp(-t/tau), tau = eta/E; the modulus E is recovered only when the tip radius is provided (spherical contact proportionality, documented); tau recovered within 2% on clean phantoms; the model cannot represent bounded solid creep (documented).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: s / Pa

- parameters:
  - `response` (positional, required) — Relaxation response.
  - `tip_radius` (keyword_only, None) — Tip radius (m); enables E.
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.MODEL.POWER_LAW

- operation_id: `force.visco.model.power_law`
- public_name: `fit_power_law_relaxation`
- public_import: `spmkit.core.analysis:fit_power_law_relaxation`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Power-law relaxation fit n(t) = (t/t_ref)^(-alpha) with 0 < )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Power-law relaxation fit n(t) = (t/t_ref)^(-alpha) with 0 < alpha < 1 and an optional equilibrium offset; t = 0 excluded (singularity); t_ref defaults to the first positive hold time and the fit uses t >= t_ref when t_ref is given.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: s

- parameters:
  - `response` (positional, required) — Relaxation response.
  - `t_ref` (keyword_only, None) — Reference time (s).
  - `with_equilibrium` (keyword_only, False) — Add the equilibrium offset.
  - `tip_radius` (keyword_only, None) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.MODEL.SLS

- operation_id: `force.visco.model.sls`
- public_name: `fit_standard_linear_solid`
- public_import: `spmkit.core.analysis:fit_standard_linear_solid`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Standard linear solid fit on a relaxation response n(t) = 1 )
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Standard linear solid fit on a relaxation response n(t) = 1 - a(1 - exp(-t/tau_relax)) or a creep response increment (dJ)(1 - exp(-t/tau_retard)); both representations are reported with the conversions J0 = 1/E0, J_inf = 1/E_inf, tau_retard = tau_relax * E0/E_inf; absolute moduli need the tip radius for the relaxation form; the creep absolute level is contact-coordinate limited (recovery reported on the increment).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa / m/N / s

- parameters:
  - `response` (positional, required) — Relaxation or creep response.
  - `tip_radius` (keyword_only, None) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `tau_initial` (keyword_only, None) — Time-constant start (s).

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.PROTOCOL.IDENTIFY

- operation_id: `force.visco.protocol.identify`
- public_name: `identify_viscoelastic_protocol`
- public_import: `spmkit.core.analysis:identify_viscoelastic_protocol`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Identifies the viscoelastic protocol of a force curve: rate-)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Identifies the viscoelastic protocol of a force curve: rate-region classification (median-of-nonzero-rate thresholds) into LOADING_RAMP, UNLOADING_RAMP, DISPLACEMENT_HOLD, FORCE_HOLD, CREEP, STRESS_RELAXATION, TRIANGULAR_LOADING, INSUFFICIENT_PROTOCOL, AMBIGUOUS_PROTOCOL; trusted instrument labels in curve.metadata take precedence; a displacement hold with a decaying force is STRESS_RELAXATION, a force hold with a drifting displacement is CREEP; missing time raises MISSING_TIME (reconstructed clock only via assume_uniform_rate); duplicate time samples raise DUPLICATE_TIMESTAMPS; the JPK/NID readers do not populate segment time, so time-domain analysis requires an explicit time axis or an explicitly requested known-rate reconstruction (no automatic general reader time-domain analysis is claimed).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `curve` (positional, required) — Force curve.
  - `contact_index` (keyword_only, None) — Contact index (height axis).
  - `contact_coordinate` (keyword_only, None) — Contact coordinate (m).
  - `rate_threshold` (keyword_only, 0.05) — Relative rate threshold.
  - `min_hold_points` (keyword_only, 5) — Minimum hold run length.
  - `min_hold_fraction` (keyword_only, 0.05) — Minimum hold fraction.
  - `assume_uniform_rate` (keyword_only, None) — Reconstructed clock (s/sample).
  - `force_threshold_fraction` (keyword_only, 0.1) — Relaxation decay threshold.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

- known deviations:
  - the protocol recommendation and ambiguity policy is SOFTWARE_VERIFIED

## FORCE.VISCO.RATE.INDENTATION

- operation_id: `force.visco.rate.indentation`
- public_name: `compute_indentation_rate`
- public_import: `spmkit.core.analysis:compute_indentation_rate`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Robust indentation and force rate of one protocol region: me)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Robust indentation and force rate of one protocol region: median of the local finite-difference rates with the 25-75 percentile spread; region located via the protocol result; missing region raises EMPTY_REGION; requires a valid time axis (the JPK/NID readers do not populate segment time; provide one or use an explicitly requested known-rate reconstruction); units m/s and N/s.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: m/s

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `protocol` (positional, required) — Protocol result.
  - `region` (keyword_only, 'loading') — Region kind.
  - `segment` (keyword_only, 'extend') — Segment name.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.RELAXATION.EXTRACT

- operation_id: `force.visco.relaxation.extract`
- public_name: `extract_stress_relaxation`
- public_import: `spmkit.core.analysis:extract_stress_relaxation`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Extracts the normalized stress-relaxation response of a disp)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Extracts the normalized stress-relaxation response of a displacement hold: F(t)/F(t0) on the relative hold time with the hold indentation and force histories; equilibrium-force estimate = mean of the last tail fraction (documented estimate, not a guaranteed equilibrium); missing hold raises EMPTY_REGION; zero hold-start force raises INVALID_RESPONSE.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: s / m / N

- parameters:
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `protocol` (positional, required) — Protocol result.
  - `segment` (keyword_only, 'extend') — Segment name.
  - `hold_kind` (keyword_only, 'hold_displacement') — Hold region kind.
  - `equilibrium_tail_fraction` (keyword_only, 0.1) — Equilibrium tail fraction.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.SENSITIVITY

- operation_id: `force.visco.sensitivity`
- public_name: `analyze_viscoelastic_sensitivity`
- public_import: `spmkit.core.analysis:analyze_viscoelastic_sensitivity`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Deterministic multiverse over contact offsets, hold-boundary)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Deterministic multiverse over contact offsets, hold-boundary offsets and equilibrium-tail fractions (bounded at max_configurations) for the SLS fit on the extracted response; one-at-a-time contact/boundary/window indices relative to the baseline configuration and a dominant-source classification (contact / boundary / window / none at the 20% threshold); raw configurations and failures exposed; the interpretation is SOFTWARE_VERIFIED.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: not_applicable

- parameters:
  - `curve` (positional, required) — Force curve.
  - `prepared` (positional, required) — FS-F1 prepared curve.
  - `protocol` (keyword_only, None) — Protocol result.
  - `contact_offsets` (keyword_only, [-2, 0, 2]) — Contact offsets (samples).
  - `boundary_offsets` (keyword_only, [-3, 0, 3]) — Hold-boundary offsets.
  - `equilibrium_tail_fractions` (keyword_only, [0.05, 0.1, 0.2]) — Equilibrium tail fractions.
  - `max_configurations` (keyword_only, 96) — Multiverse bound.
  - `tip_radius` (keyword_only, None) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VISCO.VOLUME

- operation_id: `force.visco.volume`
- public_name: `fit_force_volume_viscoelasticity`
- public_import: `spmkit.core.analysis:fit_force_volume_viscoelasticity`
- family: FORCE
- maturity: SOFTWARE_VERIFIED
- status: stable
- reference: SPMKit native (Per-curve identify -> prepare -> extract -> SLS mapping over)
- evidence profile: `NATIVE_SPMKIT_DESIGNED_HEURISTIC`

- contract: Per-curve identify -> prepare -> extract -> SLS mapping over a ForceVolume: modulus_0/modulus_inf/viscosity/relaxation-time maps, model/ambiguity/sensitivity/protocol maps and an explicit failed mask with per-index reasons (nothing silently dropped); deterministic replay; viscosity = E0 * a * tau_relax (SLS dashpot estimate, documented model quantity).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa / Pa*s / s

- parameters:
  - `volume` (positional, required) — Force volume.
  - `tip_radius` (keyword_only, None) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `min_hold_points` (keyword_only, 5) — Minimum hold run length.

- evidence:
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.json`
  - `tests/validation/fixtures/force_viscoelasticity/viscoelasticity_reference.npz`
  - `tests/validation/test_force_viscoelasticity_validation.py`
  - `tests/core/test_force_viscoelasticity.py`

## FORCE.VOLUME.MECHANICS

- operation_id: `force.volume.mechanics`
- public_name: `fit_force_volume_mechanics`
- public_import: `spmkit.core.analysis:fit_force_volume_mechanics`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Per-curve mechanics mapping)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Applies prepare -> indentation -> window -> model comparison to every curve of a ForceVolume; modulus/adhesion maps, chosen model map, quality map; failed curves explicitly masked (failed_mask + provenance reasons), never silently dropped; deterministic replay; units Pa / N.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: Pa

- parameters:
  - `volume` (positional, required) — Force volume.
  - `tip_radius` (keyword_only, 1e-08) — Tip radius (m).
  - `poisson` (keyword_only, 0.3 bounds=[0.0, 0.5]) — Poisson ratio.
  - `half_angle` (keyword_only, 0.3490658503988659) — Cone half-angle (rad).
  - `models` (keyword_only, ['hertz_sphere', 'dmt']) — Candidate models.
  - `min_points` (keyword_only, 20) — Minimum window size per curve.

- evidence:
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.json`
  - `tests/validation/fixtures/force_mechanics/force_mechanics_reference.npz`
  - `tests/validation/test_force_mechanics_validation.py`
  - `tests/core/test_force_mechanics.py`

## FORCE.WORK.INTEGRATE

- operation_id: `force.work.integrate`
- public_name: `integrate_force_work`
- public_import: `spmkit.core.analysis:integrate_force_work`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Force work integration)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Force integrated over tip-sample separation on the common overlap domain (contact to min of maxima); monotone interpolation; trapezoidal arithmetic; work of adhesion = retract integral; hysteresis = approach - retract; units J; INSUFFICIENT_OVERLAP and NONMONOTONIC_COORDINATE typed failures.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: J

- parameters:
  - `curve` (positional, required) — Force curve.
  - `contact` (positional, required) — Contact point result.
  - `domain` (keyword_only, 'tip_position' values=['tip_position', 'height']) — Integration domain.

- evidence:
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.json`
  - `tests/validation/fixtures/force_foundation/force_phantoms_reference.npz`
  - `tests/validation/fixtures/force_foundation/force_foundation_reference.json`
  - `tests/validation/test_force_foundation_validation.py`
  - `tests/core/test_force_foundation.py`

- known deviations:
  - real tip-sample separation is often non-monotone; the operation raises NONMONOTONIC_COORDINATE instead of fabricating a value

## FORCE.WORK.PATH_INTEGRATE

- operation_id: `force.work.path_integrate`
- public_name: `integrate_force_path_work`
- public_import: `spmkit.core.analysis:integrate_force_path_work`
- family: FORCE
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Acquisition-path force work)
- evidence profile: `NUMERICALLY_VERIFIED_NATIVE_PHANTOM_ORACLE`

- contract: Signed path work over a single trajectory in acquisition order: W = sum_i 0.5*(F_i+F_{i+1})*(z_{i+1}-z_i) with deterministic float64 accumulation; signed dz retained (local reversals and closed loops contribute their signed path work; repeated coordinates contribute zero; translation-invariant; acquisition reversal flips sign); no sorting, no abs(), no smoothing, no point deletion; complete CoordinatePathDiagnostics; classification_tolerance only classifies (direction, reversal counts), never alters the integral; NONFINITE_DATA, LENGTH_MISMATCH, INSUFFICIENT_SAMPLES, MISSING_COORDINATE typed failures.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: object
  - units: J

- parameters:
  - `coordinate` (positional, required) — Coordinate axis (e.g. tip-sample separation) in acquisition order.
  - `force` (positional, required) — Calibrated force samples (same length as coordinate).
  - `coordinate_unit` (keyword_only, 'm') — Coordinate unit label.
  - `force_unit` (keyword_only, 'N') — Force unit label.
  - `classification_tolerance` (keyword_only, '0.0') — Classification-only tolerance in SI coordinate units (never used to alter the integral).
  - `provenance` (keyword_only, None) — Provenance metadata.

- evidence:
  - `tests/core/test_force_path_work.py`

- known deviations:
  - path work is a path integral, not thermodynamic work; closed/ambiguous paths warn and split forward/backward contributions by step sign
  - absolute_accumulated_work is not dissipation energy

## IMG.FILTER.GAUSSIAN

- operation_id: `img.filter.gaussian`
- public_name: `gwyddion_gaussian_filter`
- public_import: `spmkit.core.analysis:gwyddion_gaussian_filter`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Gaussian Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Separable Gaussian smoothing with sigma in pixels; kernel resolution 2*ceil(5*sigma)+1 capped at 3*min(xres,yres) and forced odd; mirror borders; horizontal-then-vertical passes; sequential-sum reciprocal normalization (not forced to exactly 1.0).

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: mirror
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `sigma` (keyword_only, 5.0 bounds=[0.01, 40.0]) — Gaussian standard deviation in pixels.

- evidence:
  - `tests/validation/fixtures/gwyddion/neighborhood_filters/neighborhood_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/neighborhood_filters/neighborhood_filters_reference.npz`
  - `tests/validation/test_gwyddion_neighborhood_filters_production_parity.py`
  - `tests/core/test_gwyddion_neighborhood_filters.py`

- known deviations:
  - Gaussian constant-field preservation is not bitwise guaranteed; kernel-normalization rounding (~1e-15) is preserved.

## IMG.FILTER.GRADIENT_DIRECTION

- operation_id: `img.filter.gradient_direction`
- public_name: `gradient_direction`
- public_import: `spmkit.core.analysis:gradient_direction`
- family: IMG.FILTER
- maturity: NUMERICALLY_VERIFIED
- status: stable
- reference: SPMKit native (Gradient Direction (native analytical composite))
- evidence profile: `NATIVE_SPMKIT_ANALYTICAL_COMPOSITE`

- contract: Native gradient direction atan2(gy, gx) over explicit required component fields; radians; range (-pi, pi]; C99 signed-zero axes; zero vector -> +0.0; output unit rad; native analytical composite, not a Gwydion parity target; components never mutated.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: clipped
  - mutation: returns_new
  - result: SPMChannel
  - units: rad

- parameters:
  - `gx` (positional, required) — Horizontal derivative component field (finite 2D SPMChannel).
  - `gy` (positional, required) — Vertical derivative component field (finite 2D SPMChannel).

- evidence:
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz`
  - `tests/validation/fixtures/gwyddion/derivative_filters/oracle_gradient_direction_native.py`
  - `tests/validation/test_gwyddion_derivative_filters_production_parity.py`
  - `tests/core/test_gwyddion_derivative_filters.py`

- known deviations:
  - numpy.arctan2 may differ from the compiled C atan2 profile by up to ~1 ULP on some inputs; characterized by parity tests, not bitwise parity.

## IMG.FILTER.GRADIENT_MAGNITUDE

- operation_id: `img.filter.gradient_magnitude`
- public_name: `gwyddion_gradient_magnitude`
- public_import: `spmkit.core.analysis:gwyddion_gradient_magnitude`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Gradient Magnitude (hypot of component fields))
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE`

- contract: Gradient magnitude hypot(gx, gy) over explicit required component fields; reproduces the frozen hypot-of-fields orchestration; overflow/underflow-safe; +0.0 for all signed-zero component combinations; component unit retained; components never mutated.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: clipped
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `gx` (positional, required) — Horizontal derivative component field (finite 2D SPMChannel).
  - `gy` (positional, required) — Vertical derivative component field (finite 2D SPMChannel).

- evidence:
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz`
  - `tests/validation/test_gwyddion_derivative_filters_production_parity.py`
  - `tests/core/test_gwyddion_derivative_filters.py`

- known deviations:
  - Bitwise parity is bounded to the frozen platform profile x86-64 / glibc / hypot@GLIBC_2.35; no cross-libc or cross-architecture bitwise guarantee; non-negativity and component-swap symmetry hold relationally on every platform.

## IMG.FILTER.MEDIAN

- operation_id: `img.filter.median`
- public_name: `gwyddion_median_filter`
- public_import: `spmkit.core.analysis:gwyddion_median_filter`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (disc Median Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Disc median filter with footprint side `size` (2..31, even sizes valid); ellipse-inscribed footprint; upper median rank n//2; EXTEND nearest-constant borders.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: extend
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `size` (keyword_only, 5 bounds=[2, 31]) — Footprint side length (not a radius).

- evidence:
  - `tests/validation/fixtures/gwyddion/neighborhood_filters/neighborhood_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/neighborhood_filters/neighborhood_filters_reference.npz`
  - `tests/validation/test_gwyddion_neighborhood_filters_production_parity.py`
  - `tests/core/test_gwyddion_neighborhood_filters.py`

## IMG.FILTER.PREWITT_X

- operation_id: `img.filter.prewitt_x`
- public_name: `gwyddion_prewitt_x`
- public_import: `spmkit.core.analysis:gwyddion_prewitt_x`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Prewitt X Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE`

- contract: Prewitt X (horizontal) pixel-space derivative with the frozen 1/3 coefficients {1/3, 0, -1/3; 1/3, 0, -1/3; 1/3, 0, -1/3}; CLIPPED borders; frozen source sign and orientation; z-unit preserved; finite 2D inputs only; no masks or ROI.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: clipped
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.

- evidence:
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz`
  - `tests/validation/fixtures/gwyddion/derivative_filters/oracle_derivative_filters_source.py`
  - `tests/validation/test_gwyddion_derivative_filters_production_parity.py`
  - `tests/core/test_gwyddion_derivative_filters.py`

## IMG.FILTER.PREWITT_Y

- operation_id: `img.filter.prewitt_y`
- public_name: `gwyddion_prewitt_y`
- public_import: `spmkit.core.analysis:gwyddion_prewitt_y`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Prewitt Y Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE`

- contract: Prewitt Y (vertical) pixel-space derivative with the frozen 1/3 coefficients {1/3, 1/3, 1/3; 0, 0, 0; -1/3, -1/3, -1/3}; CLIPPED borders; frozen source sign and orientation; z-unit preserved; finite 2D inputs only; no masks or ROI.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: clipped
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.

- evidence:
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz`
  - `tests/validation/fixtures/gwyddion/derivative_filters/oracle_derivative_filters_source.py`
  - `tests/validation/test_gwyddion_derivative_filters_production_parity.py`
  - `tests/core/test_gwyddion_derivative_filters.py`

## IMG.FILTER.RANK

- operation_id: `img.filter.rank`
- public_name: `gwyddion_rank_filter`
- public_import: `spmkit.core.analysis:gwyddion_rank_filter`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Rank Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Rank filter with pixel radius (1..1024); ellipse-inscribed footprint in a 2*radius+1 square; rank GWY_ROUND(percentile*(n-1)); k=0/k=n-1 minimum/maximum endpoint dispatch; EXTEND borders. Public v1 exposes the primary percentile result only.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: extend
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `radius` (keyword_only, 20 bounds=[1, 1024]) — Pixel radius of the footprint.
  - `percentile` (keyword_only, 0.75 bounds=[0.0, 1.0]) — Percentile selecting the rank.

- evidence:
  - `tests/validation/fixtures/gwyddion/neighborhood_filters/neighborhood_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/neighborhood_filters/neighborhood_filters_reference.npz`
  - `tests/validation/test_gwyddion_neighborhood_filters_production_parity.py`
  - `tests/core/test_gwyddion_neighborhood_filters.py`

- known deviations:
  - Private secondary/both/difference Rank output modes are retained in diagnostics but not exposed publicly in v1.

## IMG.FILTER.SOBEL_X

- operation_id: `img.filter.sobel_x`
- public_name: `gwyddion_sobel_x`
- public_import: `spmkit.core.analysis:gwyddion_sobel_x`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Sobel X Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE`

- contract: Sobel X (horizontal) pixel-space derivative: kernel {0.25, 0, -0.25; 0.5, 0, -0.5; 0.25, 0, -0.25}; CLIPPED borders; frozen source sign (increasing-right X ramp gives negative response), orientation and accumulation order; z-unit preserved; finite 2D inputs only; no masks or ROI.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: clipped
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.

- evidence:
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz`
  - `tests/validation/fixtures/gwyddion/derivative_filters/oracle_derivative_filters_source.py`
  - `tests/validation/test_gwyddion_derivative_filters_production_parity.py`
  - `tests/core/test_gwyddion_derivative_filters.py`

## IMG.FILTER.SOBEL_Y

- operation_id: `img.filter.sobel_y`
- public_name: `gwyddion_sobel_y`
- public_import: `spmkit.core.analysis:gwyddion_sobel_y`
- family: IMG.FILTER
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Sobel Y Filter)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE`

- contract: Sobel Y (vertical) pixel-space derivative: kernel {0.25, 0.5, 0.25; 0, 0, 0; -0.25, -0.5, -0.25}; CLIPPED borders; frozen source sign (increasing-down Y ramp gives negative response), orientation and accumulation order; z-unit preserved; finite 2D inputs only; no masks or ROI.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: clipped
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.

- evidence:
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.json`
  - `tests/validation/fixtures/gwyddion/derivative_filters/derivative_filters_reference.npz`
  - `tests/validation/fixtures/gwyddion/derivative_filters/oracle_derivative_filters_source.py`
  - `tests/validation/test_gwyddion_derivative_filters_production_parity.py`
  - `tests/core/test_gwyddion_derivative_filters.py`

## IMG.INTERPOLATION.LAPLACE_UNDER_MASK

- operation_id: `img.interpolation.laplace_under_mask`
- public_name: `gwydion_interpolate_data_under_mask`
- public_import: `spmkit.core.analysis:gwydion_interpolate_data_under_mask`
- family: IMG.INTERPOLATION
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Interpolate Data Under Mask (Laplace))
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Laplace-based interpolation of masked regions; the mask selects pixels to replace; finite two-dimensional input.

- semantics:
  - mask: mask_input
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `mask` (positional, required) — Mask array selecting pixels to interpolate.

- evidence:
  - `tests/validation/fixtures/gwydion/scars_laplace/scars_laplace_reference.json`
  - `tests/validation/fixtures/gwydion/scars_laplace/scars_laplace_reference.npz`
  - `tests/validation/test_gwydion_laplace_production_parity.py`

## IMG.LEVEL.ALIGN_ROWS_MATCH

- operation_id: `img.level.align_rows_match`
- public_name: `gwyddion_align_rows_match`
- public_import: `spmkit.core.analysis:gwyddion_align_rows_match`
- family: IMG.LEVEL
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Align Rows Match)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Align Rows Match: adjacent-row shape matching with Gaussian-weighted differences of row differences, cumulative zero-levelled shifts, zero-weight guard (pure vertical offsets may remain uncorrected).

- semantics:
  - mask: include_exclude_ignore
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `mask` (keyword_only, None) — Optional mask matching the channel shape.
  - `mask_mode` (keyword_only, 'ignore' values=['exclude', 'include', 'ignore']) — Masking mode.
  - `direction` (keyword_only, 'horizontal' values=['horizontal', 'vertical']) — Row direction.

- evidence:
  - `tests/validation/fixtures/gwyddion/align_rows_remaining/align_rows_remaining_reference.json`
  - `tests/validation/fixtures/gwyddion/align_rows_remaining/align_rows_remaining_reference.npz`
  - `tests/validation/test_gwydion_align_rows_remaining_production_parity.py`

## IMG.LEVEL.ALIGN_ROWS_MODUS

- operation_id: `img.level.align_rows_modus`
- public_name: `gwyddion_align_rows_modus`
- public_import: `spmkit.core.analysis:gwyddion_align_rows_modus`
- family: IMG.LEVEL
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Align Rows Modus)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Align Rows Modus: robust row-centre statistic (global masked-median fallback, upper median for fewer than nine retained samples, narrowest sqrt-count range window otherwise), zero-levelled shifts.

- semantics:
  - mask: include_exclude_ignore
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `mask` (keyword_only, None) — Optional mask matching the channel shape.
  - `mask_mode` (keyword_only, 'ignore' values=['exclude', 'include', 'ignore']) — Masking mode.
  - `direction` (keyword_only, 'horizontal' values=['horizontal', 'vertical']) — Row direction.

- evidence:
  - `tests/validation/fixtures/gwyddion/align_rows_remaining/align_rows_remaining_reference.json`
  - `tests/validation/fixtures/gwyddion/align_rows_remaining/align_rows_remaining_reference.npz`
  - `tests/validation/test_gwydion_align_rows_remaining_production_parity.py`

## IMG.LEVEL.ALIGN_ROWS_POLYNOMIAL

- operation_id: `img.level.align_rows_polynomial`
- public_name: `gwyddion_align_rows_polynomial`
- public_import: `spmkit.core.analysis:gwyddion_align_rows_polynomial`
- family: IMG.LEVEL
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Align Rows Polynomial)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Align Rows Polynomial: degree 0 uses the trim-fraction-zero row-shift path; degree >=1 fits each row independently on centred x with a packed Cholesky solve and full-field mean anchoring.

- semantics:
  - mask: include_exclude_ignore
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `degree` (keyword_only, 1 bounds=[0, 5]) — Polynomial degree.
  - `mask` (keyword_only, None) — Optional mask matching the channel shape.
  - `mask_mode` (keyword_only, 'ignore' values=['exclude', 'include', 'ignore']) — Masking mode.
  - `direction` (keyword_only, 'horizontal' values=['horizontal', 'vertical']) — Row direction.

- evidence:
  - `tests/validation/fixtures/gwyddion/align_rows_remaining/align_rows_remaining_reference.json`
  - `tests/validation/fixtures/gwyddion/align_rows_remaining/align_rows_remaining_reference.npz`
  - `tests/validation/test_gwydion_align_rows_remaining_production_parity.py`

## IMG.SCANLINE.MARK_SCARS

- operation_id: `img.scanline.mark_scars`
- public_name: `gwydion_mark_scars`
- public_import: `spmkit.core.analysis:gwydion_mark_scars`
- family: IMG.SCANLINE
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Mark Scars)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Detect and mark scan-line scars, returning a mask array; threshold and geometry parameters follow the frozen Gwydion contract.

- semantics:
  - mask: mask_output
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: ndarray
  - units: mask

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `threshold_high` (keyword_only, 0.666) — High threshold.
  - `threshold_low` (keyword_only, 0.25) — Low threshold.
  - `min_length` (keyword_only, 16) — Minimum scar length.
  - `max_width` (keyword_only, 4) — Maximum scar width.
  - `polarity` (keyword_only, 'both' values=['positive', 'negative', 'both']) — Scar polarity.
  - `existing_mask` (keyword_only, None) — Optional existing mask.
  - `combine` (keyword_only, 'replace' values=['replace', 'union', 'intersection']) — Mask combination mode.

- evidence:
  - `tests/validation/fixtures/gwydion/scars_laplace/scars_laplace_reference.json`
  - `tests/validation/fixtures/gwydion/scars_laplace/scars_laplace_reference.npz`
  - `tests/validation/test_gwydion_mark_scars_production_parity.py`

## IMG.SCANLINE.REMOVE_SCARS

- operation_id: `img.scanline.remove_scars`
- public_name: `gwydion_remove_scars`
- public_import: `spmkit.core.analysis:gwydion_remove_scars`
- family: IMG.SCANLINE
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Remove Scars)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Detect and remove scan-line scars, returning a corrected channel; threshold and geometry parameters follow the frozen Gwydion contract.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `threshold_high` (keyword_only, 0.666) — High threshold.
  - `threshold_low` (keyword_only, 0.25) — Low threshold.
  - `min_length` (keyword_only, 16) — Minimum scar length.
  - `max_width` (keyword_only, 4) — Maximum scar width.
  - `polarity` (keyword_only, 'both' values=['positive', 'negative', 'both']) — Scar polarity.

- evidence:
  - `tests/validation/fixtures/gwydion/scars_laplace/scars_laplace_reference.json`
  - `tests/validation/fixtures/gwydion/scars_laplace/scars_laplace_reference.npz`
  - `tests/validation/test_gwydion_remove_scars_production_parity.py`

## IMG.SCANLINE.STEP_BLOCK_CORRECTION

- operation_id: `img.scanline.step_block_correction`
- public_name: `gwydion_step_block_correction`
- public_import: `spmkit.core.analysis:gwydion_step_block_correction`
- family: IMG.SCANLINE
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Step Block Correction)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Correct step-block artefacts in scan lines; threshold and direction parameters follow the frozen Gwydion contract.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.
  - `threshold` (keyword_only, 2.0) — Step detection threshold.
  - `direction` (keyword_only, 'left_to_right' values=['left_to_right', 'right_to_left']) — Scan direction.

- evidence:
  - `tests/validation/fixtures/gwydion/step_block/step_block_reference.json`
  - `tests/validation/fixtures/gwydion/step_block/step_block_reference.npz`
  - `tests/validation/test_gwydion_step_block_production_parity.py`

## IMG.SCANLINE.STEP_LINE_CORRECTION

- operation_id: `img.scanline.step_line_correction`
- public_name: `gwydion_step_line_correction`
- public_import: `spmkit.core.analysis:gwydion_step_line_correction`
- family: IMG.SCANLINE
- maturity: CROSS_VALIDATED
- status: stable
- reference: Gwydion 2.71 (Step Line Correction)
- evidence profile: `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`

- contract: Correct step-line artefacts in scan lines; no parameters beyond the input channel.

- semantics:
  - mask: none
  - ROI: no
  - NaN policy: reject
  - border: not_applicable
  - mutation: returns_new
  - result: SPMChannel
  - units: preserved

- parameters:
  - `channel` (positional, required) — Finite two-dimensional input channel.

- evidence:
  - `tests/validation/fixtures/gwydion/linecorrect/linecorrect_reference.json`
  - `tests/validation/fixtures/gwydion/linecorrect/linecorrect_reference.npz`
  - `tests/validation/test_gwydion_linecorrect_production_parity.py`
