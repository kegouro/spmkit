# SPMKit Capability Ledger

Stable scientific capabilities registered by the Operation Registry v1.

- schema_version: 1
- operations: 30

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
