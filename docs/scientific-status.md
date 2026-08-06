# Scientific status

This page is the authoritative public map from SPM-Kit capabilities to the
evidence that currently supports them. It deliberately separates implementation,
software tests, numerical recovery, external comparison, and physical validation.

## Maturity vocabulary

<div class="spm-evidence-ladder" role="list" tabindex="0" aria-label="SPM-Kit scientific evidence levels zero through five">
  <div class="spm-evidence-level spm-evidence-level--0" role="listitem"><span class="spm-evidence-level__number">0</span><strong>CLAIMED</strong><small>Documented intent only</small></div>
  <div class="spm-evidence-level spm-evidence-level--1" role="listitem"><span class="spm-evidence-level__number">1</span><strong>SOFTWARE_<wbr>VERIFIED</strong><small>Scoped automated tests</small></div>
  <div class="spm-evidence-level spm-evidence-level--2" role="listitem"><span class="spm-evidence-level__number">2</span><strong>NUMERICALLY_<wbr>VERIFIED</strong><small>Known-value recovery</small></div>
  <div class="spm-evidence-level spm-evidence-level--3" role="listitem"><span class="spm-evidence-level__number">3</span><strong>CROSS_<wbr>VALIDATED</strong><small>Frozen external comparison</small></div>
  <div class="spm-evidence-level spm-evidence-level--4 spm-evidence-level--unclaimed" role="listitem"><span class="spm-evidence-level__number">4</span><strong>PHYSICALLY_<wbr>VALIDATED</strong><small>Not generally claimed</small></div>
  <div class="spm-evidence-level spm-evidence-level--5 spm-evidence-level--unclaimed" role="listitem"><span class="spm-evidence-level__number">5</span><strong>REPRODUCIBILITY_<wbr>VALIDATED</strong><small>Not generally claimed</small></div>
</div>

| Level | Required meaning |
|---|---|
| <span class="spm-level spm-level--0" data-level="0">CLAIMED</span> | A claim or intended behavior is documented, but executable evidence is not preserved. |
| <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | The behavior is exercised by automated software tests. |
| <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> | Known values are recovered within a stated numerical scope and tolerance. |
| <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> | Results are compared with an external software or reference route under a frozen protocol. |
| <span class="spm-level spm-level--4 spm-level--unclaimed" data-level="4">PHYSICALLY_VALIDATED</span> | A physical reference or experiment supports the capability within a stated scope. No general SPM-Kit claim is current. |
| <span class="spm-level spm-level--5 spm-level--unclaimed" data-level="5">REPRODUCIBILITY_VALIDATED</span> | An independent party reproduced the result under the declared protocol. No general SPM-Kit claim is current. |

The level belongs to a particular claim, campaign, data family, metric, version,
and tolerance. It never transfers automatically to an adjacent feature.

## Capability matrix

| Capability | Implementation | Evidence | Level | Independent reference | Known limitation / next requirement |
|---|---|---|---|---|---|
| Sa, Sq, Sz on frozen synthetic matrices | `core.analysis.roughness` | 48 cases, 144/144 comparisons within `atol=1e-6 nm + rtol=1e-6` | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> | Gwyddion 2.71 library route through a frozen harness-authored wrapper | Shared matrices, no preprocessing, three metrics only; not physical validation or universal equivalence |
| Sa, Sq, Sz on public experimental GWY matrices | `core.analysis.roughness` | 12 cases, 36/36 shared-matrix comparisons within tolerance | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> for the shared-matrix algorithm track | Gwyddion 2.71 | Parser/end-to-end observations are separate: 10 equivalences and 2 preserved channel-count differences |
| Limited Nanoscope III `.spm` images | `core.io.bruker_spm` | Six demonstrated files; 18/18 Sa/Sq/Sz comparisons within tolerance and zero reported pixel delta | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> | Gwyddion 2.71 | `ACCIDENTAL_PRE_FREEZE_UNBLINDING`; partial variants only, no blind holdout or general Bruker support |
| NanoSurf `.nid` mapping and orientation | `core.io.nid`, `core.verify` | Synthetic byte-budget/orientation tests and selected lab-context comparisons | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span>; selected comparisons do not establish universal format coverage | Gwyddion exports for selected files | Private instrument corpus is not distributed; additional redistributable multi-instrument fixtures are needed |
| Gwyddion Flatten Base end-to-end trajectory | `core.analysis._flatten_base` | Focal LM and packed-Cholesky verification plus a frozen Gwyddion 2.71 end-to-end fixture; matching facet/polynomial control flow and corrected-field maximum absolute difference `1.465494e-14` | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> | Gwyddion 2.71 executable | Internal Core path and one frozen end-to-end trajectory plus focused numerical cases; no universal equivalence claim across datasets, parameter regimes, platforms or Gwyddion versions |
| Physical arc-revolution background | `core.analysis.background` | 55 unit and synthetic tests, including a test-local brute-force 1D oracle, inversion duality, physical-unit equivalence, anisotropic spacing, border policies and reconstruction identity | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | None | Python API only; finite geometric Z data; no masks, Gwyddion equivalence or physical-reference campaign |
| Gwyddion-compatible Revolve Arc background | `core.analysis.background`, `core.analysis._gwyddion_arc_revolution` | Frozen Gwyddion 2.71 source semantics, focal kernel probes, one asymmetric 5×7 directional fixture, 6/6 background routes and 5/5 valid corrected routes within `5e-14`; repaired reconstruction for the defective horizontal-inverted wrapper | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> for the frozen campaign | Gwyddion 2.71 source, compiled probes and frozen JSON/NPZ fixture | Radius is in samples; no masks or non-finite data; one-sample processing axes use a documented safe definition; no physical validation, tip reconstruction, performance equivalence or universal-equivalence claim |
| Physical sphere-revolution background | `core.analysis.background` | 51 unit and synthetic tests, including independent brute-force 2D oracles for nearest and reflect borders, physical anisotropy, non-separability, unit equivalence and reconstruction identity | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | None | Python API only; finite geometric Z data; no masks, Gwyddion equivalence, performance campaign or physical-reference campaign |
| Gwyddion-compatible Sphere-revolution background | `core.analysis.background`, `core.analysis._gwyddion_sphere_revolution` | Frozen Gwyddion 2.71 source semantics, focal probes, 10 original surfaces, 10 normal executions on negated inputs (20 valid external runs per build), 15/15 inverted runs failing in normal build and under ASan; direct external reference for normal, derived external cross-validation for inverted background, safe deliberate divergence for inverted corrected (`atol=5e-14`, `rtol=0.0`); independent Python oracle | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> for the frozen campaign | Gwyddion 2.71 source, compiled probes, independent Python oracle and frozen JSON/NPZ fixture | Radius is in samples; no non-finite data or masks; inverted corrected does not claim equivalence with Gwyddion's crashing wrapper; no physical validation, tip deconvolution or universal-equivalence claim; physical sphere-revolution maintains its independent software verification |
| Gwyddion 2.71 Median Background | `core.analysis.background`, `core.analysis._median_background` | Frozen executable reference campaign: 36 logical cases, 72 executions (36 normal, 36 ASan), radii 1/2/3/4/20/1024, direct and radixtree reference paths; public background and corrected fields 36/36 bitwise exact, maximum absolute difference 0 and maximum ULP 0; input mutation maximum 0 and reconstruction maximum `4.4408920985006262e-16` | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 36-case campaign | Gwyddion 2.71 source, executable probe, independent Python oracle, frozen NPZ/JSON fixture | Finite two-dimensional inputs only; no universal equivalence, performance-equivalence, future-Gwyddion, all-radii, or all-matrices claim; `rank_backend_reference` describes Gwyddion, not an SPM-Kit backend |
| Gwyddion 2.71 Filter flat-disc morphology | `core.analysis.background`, `core.analysis._gwyddion_flat_disc_morphology` | Frozen executable reference campaign: 12 fields, six sizes 2/3/4/5/30/31, 72 Opening and 72 Closing cases; kernels 30/30, Opening 72/72 and Closing 72/72 bitwise exact; maximum absolute difference 0, maximum ULP 0, signed-zero mismatches 0, input mutation 0 | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen campaign | Audited Gwyddion 2.71 executable, corrected external probe V3, executable reduction trace, independent oracle V2, frozen NPZ/JSON fixture | Finite full-field data with masks ignored; no universal equivalence, NaN/Inf, ROI, masks, ASF, tip morphology, physical rolling-ball, performance, other builds/versions, public erosion/dilation, or source-only tie claim |
| Gwyddion 2.71 Path Level | `core.analysis.leveling`, `core.analysis._gwyddion_path_level` | Audited executable campaign: 18 base families, thicknesses 1/2/3/128, 72 logical cases, 144 fresh external executions and 72 deterministic repeat pairs; private and public arrays 72/72 bitwise exact, 4,652/4,652 elements exact, max absolute/ULP 0, signed-zero mismatches 0, normalized endpoints and mutation/no-op classifications 72/72 | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen campaign | Audited Gwyddion 2.71 Path Level tool, external probe, independent oracle V1, frozen NPZ/JSON fixture | Finite non-empty full fields and ordered straight selections only; no universal equivalence, NaN/Inf, masks/ROI, paths/splines, profiles, align-rows, volume, GUI, performance, or other-build/version claim |
| Gwyddion 2.71 Align Rows statistics | `core.analysis.leveling`, `core.analysis._gwyddion_align_rows_statistics` | Public 64-case finite campaign: portable source semantics 64/64 arrays and 3,888/3,888 elements bitwise exact; installed fast-math profile 61/64 arrays and 3,757/3,888 elements exact, with only three signed-zero and 128 independently explained reassociation differences | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen dual-profile campaign | Gwyddion 2.71 source, external executable probe, independent portable V2 oracle, frozen NPZ/JSON fixture, installed-build diagnosis | Four methods only; finite full fields, frozen masks/directions/trims; no universal, non-finite, performance, other-version/build, GUI, or generic-`align_rows` compatibility claim |
| Gwyddion 2.71 Align Rows Facet-level tilt | `core.analysis.leveling`, `core.analysis._gwyddion_align_rows_facet_tilt` | Public 15-case finite campaign: 15/15 corrected arrays (377 elements) bitwise exact against independent oracle and compiled Gwyddion 2.71 source-inclusion probe; 3 background arrays verified elementwise; shifts confirmed all-zero with source-correct length (original rows horizontal, original columns vertical, 7-length VERTICAL shifts for the 5x7 case); mask EXCLUDE/INCLUDE/IGNORE predicates, HORIZONTAL/VERTICAL directions, and fractional mask boundary behavior verified | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 15-case campaign | Gwyddion 2.71 source (compiled source-inclusion probe), independent Python oracle, frozen NPZ/JSON fixture | Facet-level tilt method only; finite inputs (NaN/inf rejected at entry); no trim-fraction, degree, or other method-family claim; no universal, performance, other-version/build, or GUI claim |
| Gwydion 2.71 Step Line Correction | `core.analysis.scanline`, `core.analysis._gwydion_step_line_correction` | Public 16-case finite campaign: production kernel 176/176 arrays and 5,046/5,046 elements bitwise exact against the compiled source-inclusion probe and independent oracle; max absolute difference 0, max ULP 0, signed-zero mismatches 0; two-pass distinguishing case and conservative-filter dimension behaviour verified | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 16-case campaign | Compiled Gwydion 2.71 source-included kernels with source-pinned orchestration, independent Python oracle, frozen JSON/NPZ fixtures, normal and ASan+UBSan campaign | Horizontal row processing only; finite inputs only (NaN/Inf rejected at entry); no input mask; no parameterized threshold; no Block Line Correction; no GUI, undo or logging parity; no universal or other-version/build equivalence; potentially destructive transformation; no claim of preserving quantitative roughness, PSD or morphology |
| Gwydion 2.71 Mark Inverted Rows | `core.analysis.scanline`, `core.analysis._gwydion_mark_inverted_rows` | Public 14-case finite campaign: production kernel 59/59 arrays and 596/596 elements bitwise exact against the compiled source-inclusion probe and independent oracle; exact binary masks, marked-row sets, guards, strict-first anchor tie, early-return and existing-mask overwrite classifications; data field non-mutation verified | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 14-case campaign | Compiled Gwydion 2.71 source-included kernels with source-pinned orchestration, independent Python oracle, frozen JSON/NPZ fixtures, normal and ASan+UBSan campaign | Horizontal rows only; finite inputs only; no persistent Data Browser mask state (public API returns an independent mask, all-zero when Gwydion would create none); no interpolation or automatic correction; no claim that a marked row should be numerically sign-inverted; no other version/build or universal equivalence |
| Gwydion 2.71 Mark Scars | `core.analysis.scanline`, `core.analysis._gwydion_mark_scars` | Production 22-case finite campaign: 20 public-API cases and two private-kernel semantic cases; production masks 22/22 arrays and 1,726/1,726 elements bitwise exact against the compiled probe and independent oracle; max absolute difference 0, max ULP 0, signed-zero mismatches 0; exact parameter and combine semantics (replace/union/intersection), effective-threshold sanitization, hard/soft seeding, width/length boundaries, outer-row exclusion and no-detection classifications verified | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 22-case campaign | Compiled-against Gwydion 2.71 libprocess 2.71 (pinned shared-library hash, frozen source identity), independent Python oracle, frozen JSON/NPZ fixtures, normal and ASan+UBSan probe campaign | Detector, not proof of physical corruption; horizontal scan-line scars only (no vertical orientation); finite fields only (NaN/Inf rejected at entry); thresholds within [0,2], min_length [1,1024], max_width [1,16]; no Data Browser mask persistence; no roughness or morphology preservation claim; no other version/build or universal equivalence |
| Gwydion 2.71 Interpolate Data Under Mask (Laplace) | `core.analysis.interpolation`, `core.analysis._gwydion_laplace` | Production 18-case finite campaign with explicitly mixed comparison classes: exact policies (empty mask unchanged, whole-field mask zeros, strict mask>0 predicate, calibration independence, unmasked pixels bitwise unchanged) and source-compatible special paths bitwise; campaign maximum 2 ULP and 1.7763568394002505e-15 absolute difference against the linked 2.71 library on the retained iterative paths; zero exact-zero/nonzero transitions in the retained Laplace cases; independent Decimal mathematical reference; production residual guard (implementation numerical-quality guard, not compiled-residual parity); L05/L06 one-ULP tridiagonal rounding classified; L17 signed-zero build-specific classification (production matches the compiled -0.0) | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 18-case campaign, with explicitly mixed comparison classes | Compiled-against Gwydion 2.71 libprocess 2.71 (pinned shared-library hash, frozen source identity), independent Decimal mathematical oracle, frozen JSON/NPZ fixtures, normal and ASan+UBSan probe campaign | Finite values only; mask >0 semantics; no qprec API (process operation grain_id=-1, qprec=1.0); implementation solves the same discrete problem but does not claim algorithmic identity with Gwydion's multilevel/CG/Jacobi solver; no uncertainty; no preservation claim for roughness, PSD, autocorrelation or morphology; no physical validation; no universal tolerance or other-build equivalence; linked library internals were not sanitizer-instrumented |
| Gwydion 2.71 Remove Scars | `core.analysis.scanline`, `core.analysis._gwydion_remove_scars` | Production 6-case finite composition campaign: production temporary mask 6/6 bitwise identical to the frozen compiled mask; production result equals the explicit production Mark-plus-Laplace composition; compiled mask and composition identities frozen 6/6 bitwise; corrected-field compatibility uses mixed comparison classes: the no-detection case is bitwise unchanged, and 128 exact-zero versus tiny-nonzero transitions (compiled values exact zero, production magnitudes at most ~1.739e-15, independent mathematical reference exact zero) satisfy the frozen absolute-difference bound, not the finite-nonzero ULP bound | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 6-case composition campaign | Compiled-against Gwydion 2.71 libprocess 2.71 (pinned shared-library hash, frozen source identity), independent oracle composition, frozen JSON/NPZ fixtures, normal and ASan+UBSan probe campaign | Inherits all Mark and Laplace limitations; temporary mask is private; no existing-mask or combine parameter; no claim that detected/interpolated data are physically recovered; no other version/build or universal equivalence |
| Gwydion 2.71 Step Block Correction | `core.analysis.scanline`, `core.analysis._gwydion_step_block` | Production 28-case finite campaign: public corrected fields 28/28 bitwise exact against the frozen compiled probe; private diagnostics (effective threshold, discontinuity and block preview masks, row split states, boundary topology, block shifts, 25%-trimmed-mean raw and post-selection arrays, retained sums, cumulative correction) exact where compared; xres=1 explicitly rejected as a documented frozen-source defect (out-of-bounds read) | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen 28-case domain (finite float64 fields, xres >= 2, threshold [0.1, 10.0], left-to-right and right-to-left directions) | Compiled Gwydion 2.71 source-included kernel with source-pinned orchestration, exact source-semantic oracle, independent declarative oracle, frozen JSON/NPZ fixtures, normal and ASan+UBSan probe campaign | No parity for xres=1; finite inputs only; no NaN/Inf compatibility; no mask input; no universal Gwydion-version equivalence; no GUI black-box execution; no physical or experimental validation; no preservation claim for roughness, PSD, morphology or real terraces; no proof that a detected step is an acquisition artefact; no uncertainty quantification; no universal bitwise equivalence outside the frozen campaign |
| Hertz / conical contact and DMT paths | `core.analysis.forcecurve` | Unit and synthetic-recovery tests; Hertz/conical modulus recovery gates | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> within synthetic test scope | Analytical construction | No certified cantilever/tip calibration or broad experimental campaign |
| Adhesive JKR | `core.analysis.experimental` | Synthetic recovery of reduced modulus and work of adhesion; Hertz-limit test | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> within synthetic scope | Analytical construction | Experimental module; no physical-reference campaign |
| WLC and FJC chain models | `core.analysis.chain` | Analytical synthetic-recovery tests | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> within synthetic scope | Analytical construction | No cross-software or experimental population campaign |
| SLS relaxation | `core.analysis.experimental` | Synthetic recovery of characteristic time and elastic limit | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> within synthetic scope | Analytical construction | Loader/UI path for pause segments remains limited |
| Force-volume property maps | `core.analysis.forcevolume*` | Scalar/vectorized consistency and synthetic modulus-map recovery tests | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> within synthetic scope | Internal scalar and analytical controls | Not an independent reference; experimental calibration remains user supplied |
| KPFM / CPD | `core.analysis.kpfm` | Unit tests for CPD and work-function calculation | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | None | No public physical-reference campaign |
| PSD, correlation, fractal estimates | `core.analysis.spectral` | Unit and synthetic tests | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | None | Definitions and preprocessing must be matched before external comparison |
| Grain detection | `core.analysis.grains` | Synthetic morphology tests | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | None | Threshold-dependent; no universal segmentation benchmark |
| SHO resonance and thermal calibration utilities | `core.analysis.resonance`, `calibration` | Unit and numerical tests; limited experimental exercise is documented separately | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span>; no general physical claim | None for a frozen public campaign | Requires a redistributable calibrated reference and frozen acquisition context |
| Fathom workspace | `gui/` over public core APIs | Offscreen GUI tests plus architecture tests | <span class="spm-level spm-level--1" data-level="1">SOFTWARE_VERIFIED</span> | None | Platform/Qt behavior can vary; GUI evidence does not upgrade numerical maturity |

## Canonical campaign records

- [48-case Gwyddion roughness summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/gwyddion_roughness_48_v0.1_summary.json)
- [Public experimental GWY pilot summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/real_data_roughness_pilot_v0.1_summary.json)
- [Nanoscope `.spm` pilot summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/nanoscope_spm_parser_pilot_v0.1_summary.json)
- [Nanoscope incident and final audit](https://github.com/kegouro/spmkit-validation/blob/main/docs/campaigns/nanoscope_spm_parser_pilot_v0.1_audit.md)
- [Flatten Base Gwyddion 2.71 frozen end-to-end fixture](https://github.com/kegouro/spmkit/blob/flatten-base-gwyddion-parity-v1/tests/validation/fixtures/gwyddion/flatten_base/gwyddion_2_71_end_to_end.json)
- [Sphere Revolution Gwyddion 2.71 frozen fixture](https://github.com/kegouro/spmkit/blob/feat/gwyddion-leveling-parity/tests/validation/fixtures/gwyddion/sphere_revolution/sphere_revolution_reference.json)
- [Median Background Gwyddion 2.71 frozen manifest](https://github.com/kegouro/spmkit/blob/main/tests/validation/fixtures/gwyddion/median_background/median_background_reference.json)

### Gwyddion Sphere Revolution

SPM-Kit's `gwyddion_sphere_revolution` implementation is maintained separately from physical sphere revolution. It reproduces Gwyddion 2.71's Revolve Sphere numerical semantics:
- **Campaign Scope:** 10 original surface matrices across WIDE_ASYMMETRIC, TALL_ASYMMETRIC, CONSTANT_ZERO_RMS, and SIGNED_MICRO_GRID families, plus 10 normal executions on explicitly negated inputs (20 valid external runs per build).
- **Inverted Route Failure Evidence:** 15/15 executions of `inverted=True` crash in Gwyddion 2.71's C module (exit code 139 in normal build, exit code 134 under ASan at `sphere-revolve.c:328 gwy_data_field_subtract_fields`).
- **Evidence Classes:**
  - `normal` route: Direct external reference from Gwyddion 2.71 stdout.
  - `inverted` background: Derived external cross-validation from `-B(-data)`.
  - `inverted` corrected: Safe deliberate divergence (`original - background`) reconstructing original data without invoking Gwyddion's crashing subtract wrapper.
- **Independent Oracle & Tolerances:** Verified against an independent Python oracle (`atol=5e-14`, `rtol=0.0`). The maximum observed numerical discrepancy across all comparisons is `8.881784e-16` (well below `5e-14`).
- **Claim:** LEVEL 3 CROSS_VALIDATED within the frozen fixture scope. No universal equivalence or physical validation is claimed. Physical sphere revolution (`estimate_sphere_revolution_background`) maintains its independent software verification.

### Gwyddion 2.71 Median Background

**Claim:** `CROSS_VALIDATED` only for the frozen campaign. Gwyddion 2.71 is the executable
external reference; the campaign contains 36 logical cases and 72 executions (36 normal and
36 ASan) over radii 1, 2, 3, 4, 20, and 1024. Both Gwyddion reference paths are represented:
`direct` and `radixtree`. Public `estimate_gwyddion_median_background`,
`remove_gwyddion_median_background`, and `analyze_gwyddion_median_background` reproduce the
frozen background and corrected arrays bitwise in 36/36 cases: maximum absolute difference 0,
maximum ULP 0, input mutation maximum 0, and reconstruction maximum
`4.4408920985006262e-16`.

The fixed semantics are the inclusive digital ellipse, `gwyddion_border_extend`, middle rank
`kernel_active_count//2`, and `corrected = input - background`. The public API preserves the
`SPMChannel` context and requires finite two-dimensional data. The private kernel is independent
of Gwyddion at runtime. The fixture and independent Python oracle remain frozen evidence outside
production.

**Traceability:**

```text
Gwyddion 2.71 source: modules/process/median-bg.c
  → frozen external probe: median_background_behavior_probe.c
  → frozen campaign runner: run_median_background_probe_campaign.sh
  → independent Python oracle recorded by docs/design/GWYDDION_MEDIAN_BACKGROUND_COMPATIBILITY.md
  → tests/validation/fixtures/gwyddion/median_background/median_background_reference.npz
  → tests/validation/fixtures/gwyddion/median_background/median_background_reference.json
  → src/spmkit/core/analysis/_median_background.py
  → src/spmkit/core/analysis/background.py
  → tests/core/test_gwyddion_median_background_private.py
  → tests/core/test_gwyddion_median_background.py
  → tests/validation/test_median_background_fixture_integrity.py
  → docs/scientific-status.md
```

The evidence was frozen in `818dbd3` (freeze evidence), the private kernel in `a53c3bb`, and
the public API in `ed5c837`. The focal inventory is 20 fixture-integrity, 67 private Median
Background, and 72 public Median Background tests; the preceding combined focal run collected
442 tests. These are focal-campaign counts, not a project-wide total.

**Non-claims:** no universal equivalence; no guarantee outside the 36 cases; no NaN or infinity
coverage and no reproduction of Gwyddion's internal radixtree; no performance-equivalence claim;
no claim for future Gwyddion versions; no claim for every radius or matrix; and no validation of
configurable border, shape, or rank parameters because the API exposes none.

**Non-blocking tooling limitations:** the probe runner uses `|| true` during compilation and does
not retain the original compiler exit code; its auxiliary parser recognizes broad `background_`
and `corrected_` prefixes. The campaign remains valid because both binaries executed, 72
processes returned, stderr was empty, normal and ASan stdout were byte-identical, outputs were
parsed and recalculated independently, oracle/reference results were bitwise exact, and the
fixture stores canonical hashes.

### Gwyddion 2.71 Filter flat-disc morphology

**Claim:** `CROSS_VALIDATED` only within the frozen executable campaign. The audited Gwyddion
2.71 Filter path is represented by 12 deterministic finite fields at sizes 2, 3, 4, 5, 30,
and 31. Opening and Closing each match the frozen external outputs bitwise in 72/72 cases;
kernels match 30/30, maximum absolute difference and ULP distance are both 0, signed-zero
mismatches are 0, and input mutation is 0.

The fixed semantics are the K×K inclusive digital ellipse, nearest-edge extension, asymmetric
even-size anchors, and the audited executable Each/Even plus RLE reduction hierarchy. The
source strict ternaries and executable MINSD/MAXSD equality behavior are distinct; SPM-Kit
reproduces the audited executable path. The rejected uninitialised-kernel microprobe is not
evidence; the corrected zero-initialised probe is the valid external record.

**Traceability:**

```text
Gwyddion 2.71 source: libprocess/filters-minmax.c
  → frozen external probe: flat_disc_probe_v3
  → frozen reduction trace: flat_disc_reduction_trace_v1
  → independent oracle: flat_disc_morphology_oracle.py
  → tests/validation/fixtures/gwyddion/flat_disc_morphology/flat_disc_morphology_reference.npz
  → tests/validation/fixtures/gwyddion/flat_disc_morphology/flat_disc_morphology_reference.json
  → src/spmkit/core/analysis/_gwyddion_flat_disc_morphology.py
  → src/spmkit/core/analysis/background.py
  → tests/core/test_gwyddion_flat_disc_morphology_private.py
  → tests/core/test_gwyddion_flat_disc_morphology.py
  → docs/scientific-status.md
```

Evidence was frozen in `2ba366e`; the private kernel is `05c5ae4`; the public API and
documentation are recorded in `1b2d081` and `c0de811`. **Non-claims:** no universal equivalence;
no NaN or infinity coverage;
no ROI, masks, ASF, tip morphology, physical rolling-ball equivalence, performance parity,
other Gwyddion builds or versions, public erosion or dilation, or claim that source-level C
tie semantics alone reproduce the audited binary.

### Gwyddion 2.71 Path Level

**Claim:** `CROSS_VALIDATED` only within the frozen Path Level campaign against the audited
Gwyddion 2.71 tool module `tools.so`
(`4711c360dd42e3e16257bf0e86d8bd41852b43d1d34540bf097736a603146237`, Build ID
`600b16d9857946609b567704b406abcc74aea698`). The campaign contains 18 finite, non-empty,
full-field base families, thicknesses 1, 2, 3, and 128, 72 logical cases, 144 fresh external
executions, and 72/72 deterministic repeat pairs. Private and public `gwyddion_path_level`
arrays are bitwise exact in 72/72 cases and 4,652/4,652 elements: maximum absolute difference
0, maximum ULP 0, signed-zero mismatches 0, normalized endpoints 72/72, mutation/no-op
classification 72/72, and input mutation 0.

The operation consumes ordered GwySelectionLine-equivalent straight physical-coordinate segments;
duplicates and object order are significant. Its fixed executable semantics include endpoint
conversion, horizontal-line exclusion, C truncating division, inclusive thickness windows, and
left-to-right cumulative row correction. Gwyddion mutates the selected data field in place and
performs GUI publication, undo, and logging; SPM-Kit returns a new `SPMChannel` and claims no
GUI-publication parity.

**Traceability:**

```text
Gwyddion 2.71 source: modules/tools/pathlevel.c
  → installed Gwyddion 2.71 Path Level tool execution
  → frozen external probe: path_level_probe_v1
  → independent oracle: path_level_oracle_v1
  → tests/validation/fixtures/gwyddion/path_level/path_level_reference.npz
  → tests/validation/fixtures/gwyddion/path_level/path_level_reference.json
  → src/spmkit/core/analysis/_gwyddion_path_level.py
  → src/spmkit/core/analysis/leveling.py
  → tests/core/test_gwyddion_path_level_private.py
  → tests/core/test_gwyddion_path_level.py
  → tests/validation/test_path_level_fixture_integrity.py
  → docs/scientific-status.md
```

The evidence commit is `d3566ce`; the private-kernel commit is `4ead95b`. No future public or
documentation commit hash is claimed. **Non-claims:** no universal equivalence; no NaN or
infinity coverage; no masks or ROI; no GwySelectionPath, splines, or polylines; no profile
extraction, align-rows equivalence, volume line-leveling, GUI/undo/logging/selection-widget
parity, performance parity, or guarantee for other Gwyddion versions or builds.

### Gwyddion 2.71 Align Rows statistics

**Claim:** `CROSS_VALIDATED` only within the frozen finite 64-case public campaign, with sixteen
cases each for Median, Median of differences, Trimmed mean, and Trimmed mean of differences.
The production contract is `portable_source_semantics`: the public wrappers are bitwise exact to
the independent V2 oracle in `64/64` corrected arrays and `3888/3888` elements, retaining all
frozen mask modes, absent-mask routes, horizontal/vertical orientations, trim fractions `0.0`,
`0.05`, and `0.5`, mutation/no-op classifications, and deterministic output.  The wrappers return
new context-preserving `SPMChannel` instances and do not claim Gwyddion GUI, publication, undo,
or mutation behavior.

The secondary `installed_gwyddion_2_71_fast_math_profile` is external executable evidence from
`process.so` (Gwyddion 2.71 installed module)
(`c21d52375807ae096e34a3469c2f20c4c66ea3197479e13215a6d7b9d465b451`).  It is bitwise exact for
`61/64` arrays and `3757/3888` elements.  The complete and bounded exception set is three
signed-zero-only Median elements in `median__plateaus_signed_zero__10` plus 64 finite elements in
each of `median_of_differences__irregular__11` and
`trimmed_mean_of_differences__irregular__11`; their maximum absolute difference is
`5.329070518200751e-15`, with no NaN or infinity discrepancy.  All eight requested backgrounds
(`504/504` elements) are bitwise exact and mutation/no-op classifications agree `64/64`.

The installed package build diagnosis is `INSTALLED_BUILD_ROOT_CAUSE_CONFIRMED` and
`V3_NOT_JUSTIFIED`: GCC 16.1.1 `-ffast-math`, associative floating-point reassociation, and LTO
produce the two irregular difference-method residuals.  The portable source-semantic arithmetic
is deliberate; SPM-Kit does not emulate that package-specific transformation and introduces no
named-case or signed-zero patch.  The public functions are explicit alternatives to, not a
compatibility claim for, the existing generic `align_rows`.

**Traceability:**

```text
Gwyddion 2.71 source: modules/process/linematch.c
  → frozen external probe: align_rows_probe_v1
  → independent oracle: align_rows_oracle_stats_v2
  → tests/validation/fixtures/gwyddion/align_rows_statistics/
  → src/spmkit/core/analysis/_gwyddion_align_rows_statistics.py
  → src/spmkit/core/analysis/leveling.py
  → tests/core/test_gwyddion_align_rows_statistics.py
  → docs/design/GWYDDION_ALIGN_ROWS_STATISTICS_COMPATIBILITY.md
```

**Non-claims:** no universal equivalence; no NaN/Inf, other Gwyddion version or build, untested
matrix, performance, ROI/GUI, adapter, or other Align Rows method-family claim.  This finite
campaign does not establish physical validation or general SPMKit parity.

### Gwyddion 2.71 Align Rows Facet-level tilt

**Claim:** `CROSS_VALIDATED` within the frozen 15-case public campaign covering zero constant,
exactly linear, nearly linear, curved with outliers, curved with masks (INCLUDE, EXCLUDE, IGNORE),
fractional mask boundaries, horizontal/vertical directions, and two-column rows (both
orientations). The production contract is bitwise exact against both the independent Python
oracle and the compiled Gwyddion 2.71 source-inclusion probe in 15/15 corrected
arrays (377 elements). Background arrays for the three extract-background cases are verified
elementwise (`input - corrected`). Shifts arrays are confirmed all-zero (matching
`gwy_data_line_clear`) with the source-correct length: the operation resamples the shifts line
to the working field's y-resolution (`gwy_data_line_resample` in `linematch.c` `execute()`),
so horizontal processing yields original-row-length shifts while vertical processing yields
original-column-length shifts (7 for the 5x7 VERTICAL case).

The kernel implements the exact Gwyddion 2.71 `linematch_do_facet_tilt` algorithm: iterative
robust reweighted slope estimation (C=1/200 weighting, exp(q) weights, 30-iteration cap,
`|tilt/dx|<1e-6` convergence), pair-wise mask predicates (INCLUDE mask≥1.0, EXCLUDE mask≤0.0),
2-column mincount guard, transpose/restore for VERTICAL direction, and centre-pivot untilting.

Known source-confirmed behaviors: constant rows produce NaN (sigma²=0, IEEE 0/0 in exp); exactly
linear rows NaN-propagate after the first correction iteration. Input NaN/inf is rejected at
entry (deliberate defensive validation, diverging from Gwyddion's unchecked IEEE propagation).

**Repair history:** an earlier closure stored five shifts for the 5x7 VERTICAL case in the kernel,
oracle, and fixture generator while the external probe emitted seven; the generator truncated the
external evidence to the assumed original y-resolution (circular-validation failure). The repair
derived the shifts length from the source (working-field y-resolution), fixed the kernel, oracle,
and generator (which now raises on truncation), added the `two_column_vertical` external case,
re-ran the normal and ASan campaigns (15/15 cases exit 0, ASan clean, normal-vs-ASan stdout
identical), and regenerated the fixtures from fresh probe output. All 14 pre-existing
corrected/background arrays are bitwise identical before and after the repair, confirming the
shifts-length correction did not alter the correction science.

The kernel implements the exact Gwyddion 2.71 `linematch_do_facet_tilt` algorithm: iterative
robust reweighted slope estimation (C=1/200 weighting, exp(q) weights, 30-iteration cap,
`|tilt/dx|<1e-6` convergence), pair-wise mask predicates (INCLUDE mask≥1.0, EXCLUDE mask≤0.0),
2-column mincount guard, transpose/restore for VERTICAL direction, and centre-pivot untilting.

Known source-confirmed behaviors: constant rows produce NaN (sigma²=0, IEEE 0/0 in exp); exactly
linear rows NaN-propagate after the first correction iteration. Input NaN/inf is rejected at
entry (deliberate defensive validation, diverging from Gwyddion's unchecked IEEE propagation).

**Traceability:**

```text
Gwyddion 2.71 source: modules/process/linematch.c (SHA-256 79b951a1...)
  → source-inclusion probe: .reference/gwyddion-2.71/facet-tilt-parity/facet_tilt_behavior_probe.c
  → independent oracle: tests/validation/fixtures/gwyddion/facet_tilt/oracle_facet_tilt.py
  → frozen fixtures: tests/validation/fixtures/gwyddion/facet_tilt/facet_tilt_reference.{json,npz}
  → private kernel: src/spmkit/core/analysis/_gwyddion_align_rows_facet_tilt.py
  → public API: src/spmkit/core/analysis/leveling.py (gwyddion_align_rows_facet_tilt)
  → tests: tests/core/test_gwyddion_align_rows_facet_tilt.py
  → fixture integrity: tests/validation/test_gwyddion_align_rows_facet_tilt_fixture_integrity.py
```

**Non-claims:** no universal equivalence; no non-finite input propagation (rejected at entry); no
other Align Rows method-family, performance, other Gwyddion version/build, GUI, adapter, or
physical validation claim. The public function is an explicit alternative to, not a compatibility
claim for, the existing generic `align_rows`.


### Gwydion 2.71 Align Rows remaining methods (Polynomial, Modus, Match)

**Claim:** `CROSS_VALIDATED` only within the frozen compiled finite 62-case campaign with the
exact evidence profile `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`
(Gwydion 2.71 `modules/process/linematch.c` source-included kernel with source-pinned
orchestration; helper functions from the installed Gwydion 2.71 libraries).  The three public
operations are:

- `gwyddion_align_rows_polynomial` (degree `0..5`);
- `gwyddion_align_rows_modus`;
- `gwyddion_align_rows_match`.

Corrected fields are bitwise exact for all 62 canonical numerical cases at the private-kernel
level (10,056 elements, max absolute difference 0, max ULP 0) and for all 61 in-range cases
through the public API; the frozen degree-8 probe case (outside the public `0..5` degree
range) is verified only at the private-kernel level and the public API rejects it.  The
private diagnostics are exact for corrected/background/delta/shifts profiles, per-row valid
indices/counts/shifts/statuses, method and masking identity, branch selection, and signed-zero
bits.  Six determinism witnesses are stored once in the fixture NPZ with exact paired equality
relations.  Masking modes INCLUDE (`mask > 0`), EXCLUDE (`mask < 1`) and IGNORE are covered
for all three methods; inputs are finite two-dimensional channels and the input channel, data
array and mask are never mutated.  Horizontal row processing is externally `CROSS_VALIDATED`
within this compiled profile; the vertical transpose-derived direction is source-semantic and
is not claimed as externally cross-validated.

**Numerical semantics** follow the compiled evidence:

- Polynomial degree 0 uses the trim-fraction-zero **row-shift path** (per-row means,
  `mincount = GWY_ROUND(log(xres) + 1)`, global masked-median fallback, zero-levelled shifts)
  and deliberately does **not** call the degree >= 1 polynomial solver;
- Polynomial degree >= 1 fits each row independently on `x = j - 0.5*(xres-1)` with
  source-order moments, a packed lower-triangular Cholesky solve and full-field mean
  anchoring; the installed helper-library binary used for the compiled campaign performs one
  Cholesky nondiagonal step as reciprocal multiplication (`r * (1.0/s)`) where the frozen
  source text expresses direct division (`r / s`) — production follows the compiled evidence
  profile and no universal build equivalence is claimed;
- Modus is a robust row-centre statistic (global masked-median fallback, upper median for
  fewer than nine retained samples, otherwise the narrowest `sqrt(count)`-wide range window
  over the sorted samples with the mean of its central third, zero-levelled);
- Match compares adjacent rows with Gaussian-weighted differences of row differences,
  includes endpoint samples exactly, reassigns the effective weight sum before the scalar
  correction, accumulates across rows and zero-levels; under its zero-weight guard **pure
  vertical row offsets with identical row shape may remain uncorrected** — this source
  behaviour is preserved, not repaired.

**Traceability:**

```text
Gwydion 2.71 source: modules/process/linematch.c
  → compiled source-inclusion probe (normal + ASan/UBSan campaigns)
  → independent source-semantic oracle and declarative oracle
  → tests/validation/fixtures/gwyddion/align_rows_remaining/
  → src/spmkit/core/analysis/_gwyddion_align_rows_remaining.py
  → src/spmkit/core/analysis/leveling.py (public API)
  → tests/core/test_gwydion_align_rows_remaining.py
  → tests/validation/test_gwydion_align_rows_remaining_production_parity.py
```

**Non-claims:** no horizontal pixel displacement; no bidirectional channel-mismatch; no stripe
suppression; no generic outlier-line detection; no NaN/Inf compatibility; no GUI black-box
execution; no universal Gwydion version/build equivalence; no physical validation and no proof
that removed row structure is an acquisition artefact; no roughness, PSD, morphology or
uncertainty preservation claim.  This finite campaign does not establish a generic SPMKit
`align_rows` compatibility claim.

### Gwydion 2.71 Step Line Correction

**Claim:** `CROSS_VALIDATED` within the frozen 16-case finite campaign. The production kernel
(`_gwydion_step_line_correction`) is bitwise exact against the compiled Gwydion 2.71
source-inclusion probe and the independent Python oracle: 176/176 arrays and 5,046/5,046
elements bitwise exact, max absolute difference 0, max ULP 0, signed-zero mismatches 0.

**Evidence:** compiled Gwydion 2.71 source-included kernels with source-pinned orchestration
(`line_correct_step_iter`, `calculate_segment_correction` compiled verbatim from the frozen
tree; orchestration annotated per source line); independent Python oracle; frozen JSON/NPZ
fixtures; normal and ASan+UBSan 60-execution campaign (30/30 normal-versus-sanitized stdout
identical); production parity metrics; the two-pass distinguishing case `s11_pass2_change`
(pass 2 changes exactly the middle row, columns 5-10); conservative-filter dimension
behaviour (size-5 filter is a numerical no-op below 5x5, source `filters.c:1174-1177`).

**Numerical semantics** follow the frozen Gwydion 2.71 source and executable probe: row
upper-median alignment with zero-leveled shifts, two detector passes (v =
(middle-top)*(middle-bottom) > 3.0*w; segments of at least 4 equal-sign pixels; correction
(3*segment_residual + local_residual)/4), size-5 conservative denoise, global-mean
restoration. **User-facing interpretation** follows the Gwydion scan-line artefacts guide:
Step Line Correction must be described as aggressive and potentially destructive.

**Limitations and non-claims:** horizontal row processing only; finite inputs only (NaN/Inf
rejected at entry, a deliberate SPMKit policy difference); no input mask; no parameterized
threshold; no Block Line Correction; no GUI, undo or logging parity; no universal or
other-version/build equivalence; potentially destructive transformation; no claim of
preserving quantitative roughness, PSD or morphology. No experimental or physical
validation is claimed.


### Gwydion 2.71 Neighborhood Filters (Rank, disc Median, Gaussian)

**Claim:** `CROSS_VALIDATED` only within the frozen compiled finite 59-case campaign with the
exact evidence profile `COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION`
(Gwydion 2.71 frozen orchestration and source identities pinned; numerical helpers partly
supplied by installed Gwydion 2.71 libraries; probe boundary sanitizer-instrumented;
dynamically linked helper internals not sanitizer-rebuilt; `/usr/bin/gwyd*dion` not invoked;
GUI not executed; Filter Tool mask post-blending and rectangular selection excluded).  The
three public operations are:

- `gwyd*dion_rank_filter` (radius `1..1024`, percentile `0..1`; public v1 exposes the
  primary percentile result only; the private diagnostics preserve the secondary, both and
  difference source output modes);
- `gwyd*dion_median_filter` (`size` is the footprint SIDE `2..31`, not a radius; even sizes
  are valid; upper median rank `n//2`);
- `gwyd*dion_gaussian_filter` (sigma in pixels `0.01..40.0`; sigma=0 is private
  library-domain evidence and rejected publicly).

Corrected outputs and diagnostics are bitwise exact for all 59 canonical private-kernel cases
(55 public primary/tool-domain, 1 private Gaussian sigma-zero, 3 private Rank output-mode)
and for all 55 public primary cases; the 11 relation-only cases and 1 determinism witness are
verified relationally.  Inputs are finite two-dimensional channels; the input channel and
data array are never mutated (these operations take no mask).  Borders follow the fixed
source behavior: EXTEND (nearest constant) for Rank and Median, mirror extension for Gaussian.

**Numerical semantics** follow the compiled evidence:

- Rank Filter: ellipse-inscribed footprint in a `2*radius+1` square, active count `n`,
  rank `GWY_ROUND(percentile*(n-1))`, k=0/k=n-1 minimum/maximum endpoint dispatch,
  EXTEND borders, kth-rank value selection;
- disc Median: ellipse-inscribed footprint in a `size x size` square, upper median rank
  `n//2`, EXTEND borders;
- Gaussian: separable kernel `res = 2*ceil(5*sigma)+1` capped at `3*min(xres,yres)` and
  forced odd, coefficients `exp(-x^2/(2*sigma^2))`, sequential-sum normalization via
  reciprocal multiply (not forced to exactly 1.0), mirror borders, horizontal-then-vertical
  passes with the horizontal intermediate preserved.  Gaussian constant preservation is
  **not** bitwise guaranteed: the observed kernel-normalization rounding (~1e-15) is
  preserved rather than corrected.

**Non-claims:** no mask support; no rectangular selection; no Mean operation; no public
Minimum/Maximum operation; no morphology capability; no FFT/frequency filtering; no NaN/Inf
compatibility; no GUI black-box execution; no universal Gwydion build equivalence; no
physical validation; no proof that filtering improves scientific truth; no roughness, PSD,
morphology or uncertainty preservation claim.

### Gwydion 2.71 Mark Inverted Rows

**Claim:** `CROSS_VALIDATED` within the frozen 14-case finite campaign. The production kernel
(`_gwydion_mark_inverted_rows`) is bitwise exact against the compiled Gwydion 2.71
source-inclusion probe and the independent Python oracle: 59/59 arrays and 596/596 elements
bitwise exact; exact binary masks; exact marked-row sets; exact guards, early-return
classifications, strict-first anchor tie and existing-mask overwrite classifications; zero
input mutation.

**Evidence:** compiled Gwydion 2.71 source-included kernels with source-pinned orchestration;
independent Python oracle; frozen JSON/NPZ fixtures; normal and ASan+UBSan campaign; exact
binary masks (0.0/1.0); boundary and consecutive-row cases; strict-first anchor tie
(`m09_tie_anchor`); no-negative early return; existing-mask overwrite semantics validated
privately; data field non-mutation.

**Public adaptation:** SPMKit has no persistent Data Browser mask state; the public API
returns an independent C-contiguous mask array, all-zero when Gwydion would create no mask.
The private kernel preserves an existing mask untouched on the no-negative early return and
overwrites it bitwise after actual detection (modelling `linecorrect.c:255-260, 321-324`).

**Limitations and non-claims:** horizontal rows only; finite inputs only; no persistent Data
Browser mask state; no interpolation or automatic correction; no claim that a marked row
should be numerically sign-inverted; no other version/build or universal equivalence. No
experimental or physical validation is claimed.

### Gwydion 2.71 Mark Scars

The detector computes one global vertical-difference RMS
(`sqrt(sum((d[i,j]-d[i+1,j])**2)/(xres*yres))`), searches per column for bands of up to
`max_width` rows whose values lie at least `threshold_low` RMS away from their boundary
rows, keeps pixels with weight at least `threshold_high` RMS as hard seeds, attaches
adjacent soft pixels through chained horizontal expansion and retains only per-row runs of
at least `min_length` pixels. Positive scars are bands elevated above their neighbours;
negative scars are depressed bands; `"both"` runs the two detectors and unions the binary
masks. The detector is exact: the production kernel is bitwise equal to the compiled probe
and the independent oracle for all 22 cases (1,726/1,726 mask elements, zero maximum
absolute/ULP difference and zero signed-zero mismatches). Coverage is split: 20 cases
exercise the public API, while C05_soft_only_no_seed and C07_detached_soft_run are
private-kernel semantic cases. Both require `threshold_high=3.0` (a uniform single-row
band has weight sqrt(5) ~ 2.236, so a soft-only configuration needs a hard threshold
above sqrt(5)), which lies outside the public Gwyddion-compatible parameter domain
[0, 2]; they remain valid kernel-semantic tests, and the public domain is not broadened
merely to express test phantoms. Combine semantics (replace ignores the existing mask,
union is source-compatible fmax, intersection is source-compatible fmin) and the
module-level no-detection mask-presence classification are verified; combined masks may
retain finite non-binary values from an existing mask.

**Limitations and non-claims:** detector, not proof of physical corruption; horizontal
scan-line scars only; no vertical orientation; finite fields only; parameter domains match
the Gwyddion process module; SPMKit does not simulate Data Browser mask removal or
persistence; no claim of roughness or morphology preservation; no other version/build or
universal equivalence. No experimental or physical validation is claimed.

### Gwydion 2.71 Interpolate Data Under Mask (Laplace)

The public operation solves the discrete Laplace boundary-value problem for pixels with
`mask > 0`: each masked pixel equals the mean of its masked neighbours and its fixed
(unmasked) neighbours, with missing neighbours at image borders implementing Neumann
conditions. The empty mask leaves the field bitwise unchanged; a whole-field positive mask
returns the source-defined all-zero field; physical calibration does not enter the solve.
Comparison classes are explicitly mixed: exact policies and source-compatible special
paths (isolated pixels, thin tridiagonal corridors, three-pixel L components) are bitwise
against the compiled probe, while the retained generic iterative paths stay within the
frozen campaign maximum of 2 ULP and 1.7763568394002505e-15 absolute difference against
the linked 2.71 library, with zero exact-zero/nonzero transitions in the retained Laplace
cases. An independent Decimal (80-digit) mathematical reference is frozen in the
fixtures; the production residual limit (1e-13) is a production convergence and
numerical-quality guard for the frozen campaign, not compiled-residual parity. The
compiled probe residuals were measured during the campaign but are not stored in the
current persistent JSON/NPZ fixtures, and the production residual is not claimed to be
no worse than the compiled probe (L11 is approximately twice the compiled residual at the
float64 floor; L10 is equal, L12 is half). Exact compiled-residual parity is not claimed;
the persistent contract enforces output-distance metrics and the independent mathematical
residual guard. L05/L06 carry the measured one-ULP tridiagonal rounding classification;
L17 is a signed-zero build-specific classification (production reproduces the compiled
-0.0; the frozen source arithmetic seeded with 0.0 yields +0.0).

**Limitations and non-claims:** finite values only; `mask > 0` semantics; no qprec API (the
process operation uses grain_id=-1 and qprec=1.0); the implementation solves the same
discrete problem but does not claim algorithmic identity with Gwydion's multilevel
anisotropic sparse CG + damped-Jacobi + hierarchical reconstruction solver; no uncertainty;
no preservation claim for roughness, PSD, autocorrelation or morphology; no physical
validation; no universal tolerance or other-build equivalence; the linked library internals
were not sanitizer-instrumented (ASan/UBSan covered the probe executables and the call
boundary only). No experimental or physical validation is claimed.

### Gwydion 2.71 Remove Scars

The public operation is exactly the composition of the Mark Scars detector (with the same
parameter semantics) and the Laplace interpolation, with a private temporary mask that is
never exposed, mutated or stored, and no extra hidden correction. The compiled campaign
froze the composition identities bitwise (temporary mask equal to the standalone Mark
Scars mask; corrected equal to the standalone Laplace result; 6/6 cases). Production
reproduces the temporary-mask identity bitwise. Corrected-field compatibility against the
compiled Remove output uses the same mixed comparison classes as the Laplace operation:
the no-detection case is bitwise unchanged, while the retained scar cases carry 128
exact-zero versus tiny-nonzero transitions (compiled values are exact zero; production
values have magnitude at most approximately 1.739e-15; the independent mathematical
reference is exactly zero) that satisfy the frozen absolute-difference bound
(1.7763568394002505e-15), not the finite-nonzero ULP bound. Full Remove corrected-field
bitwise equivalence is not claimed.

**Limitations and non-claims:** inherits all Mark and Laplace limitations; temporary mask
is private; no existing-mask or combine parameter; no claim that detected/interpolated
data are physically recovered; no other version/build or universal equivalence. No
experimental or physical validation is claimed.

## Evidence profile (scars/Laplace campaign)

The compiled campaign evidence was produced by custom probe executables that linked the
installed Gwydion 2.71 shared library (`libgwyprocess2`, version 2.71, SHA-256
`5f5b53cb544068638d1a3be8d6703345e49d5626d3fa4791106ce11bc051d3d7`); `/usr/bin/gwydion`
was not invoked; the frozen 2.71 source identity was retained for semantic reconciliation;
ASan/UBSan covered the probe executables and the call boundary, not the shared-library
internals.

### Gwydion 2.71 Step Block Correction

Public API: `gwydion_step_block_correction(channel, *, threshold=2.0,
direction="left_to_right")` in `core.analysis.scanline`.

Evidence profile: COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION.

The operation detects per-pixel vertical jumps with a strict absolute-difference
threshold, scores row boundaries and horizontal split positions (first strict
maximum), constructs row blocks, estimates each block's shift with a 25%
trimmed mean, and applies a cumulative piecewise-constant correction anchored
at the first block, for left-to-right and right-to-left scan directions, over
finite float64 two-dimensional fields. Public
corrected fields are bitwise exact for all 28 frozen valid compiled cases, and
the private diagnostic states (effective threshold, masks, row split states,
boundaries, shifts, trimmed-mean retained arrays and sums, cumulative
correction) are exact where compared. One frozen-source defect is recorded:
for xres=1 the source minimum length truncates to zero and the first candidate
can read out of bounds; its normal output is undefined. SPMKit deliberately
rejects xres < 2 (typed ValueError) and never exposes undefined behaviour.
Maturity is CROSS_VALIDATED only within the declared domain; no claim is made
that a detected step is an acquisition artefact rather than a real topographic
discontinuity, and no preservation of roughness, PSD, morphology or uncertainty
is claimed.

## A2 derivative filters (Sobel X/Y, Prewitt X/Y, gradient magnitude, gradient direction)

The first A2 derivative-filter batch provides four exact component filters
(`gwyd*dion_sobel_x`, `gwyd*dion_sobel_y`, `gwyd*dion_prewitt_x`,
`gwyd*dion_prewitt_y`), a gradient magnitude composition
(`gwyd*dion_gradient_magnitude(gx, gy)` = `hypot(gx, gy)`) and a native
gradient direction composite (`gradient_direction(gx, gy)` = `atan2(gy, gx)`).

Sobel X/Y and Prewitt X/Y:

- CROSS_VALIDATED within:
  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE;
- exact frozen kernels (Sobel 0.25/0.5 and Prewitt 1/3 coefficients);
- CLIPPED border semantics (corners, edges, 1x1, 1xN, Nx1, non-square);
- frozen source sign and orientation (increasing-right X ramp -> negative
  Sobel X; increasing-down Y ramp -> negative Sobel Y);
- finite two-dimensional inputs only; input channels never mutated;
- all 228 canonical source-profile outputs bitwise exact (max absolute
  difference 0, max ULP 0).

Gradient magnitude:

- source-compatible `hypot` composition over explicit component fields
  (matches the frozen hypot-of-fields orchestration);
- bitwise claim bounded to the frozen x86-64 / glibc / hypot@GLIBC_2.35
  platform profile;
- no cross-libc or cross-architecture bitwise guarantee; non-negativity and
  component-swap symmetry hold relationally on every platform.

Gradient direction:

- native SPMKit analytical composite;
- `atan2(gy, gx)`, radians, range (-pi, pi], C99 signed-zero axes;
- NUMERICALLY_VERIFIED maturity;
- NOT direct Gwydion parity; the production implementation (numpy.arctan2)
  is characterized within ~1 ULP of the compiled C atan2 profile on the
  frozen platform.

Non-claims for the derivative batch:

- no process-menu normalized-image parity;
- no universal installed-Gwydion-build bitwise equivalence;
- no physical-coordinate derivative;
- no physical slope or surface-angle claim;
- no mask or ROI support;
- no NaN/Inf compatibility;
- no edge-detection or segmentation claim;
- no physical validation;
- no scientific-truth or uncertainty-preservation claim.

## Force-spectroscopy foundation (FS-F1)

The FS-F1 foundation provides a validated curve-preparation layer over the
segment-based ForceCurve model: 13 public capabilities
(identify_force_segments, calibrate_force_curve,
compute_tip_sample_separation, fit_force_baseline, correct_force_baseline,
contact_point_threshold, contact_point_ratio_of_variances,
contact_point_piecewise, contact_point_ensemble, extract_force_events,
integrate_force_work, score_force_curve_quality, prepare_force_curve) with
immutable results, typed failures and explicit provenance.

- pipeline order: segments -> calibration -> tip-sample separation ->
  baseline fit/correction -> contact ensemble -> events -> work -> quality;
- units: height/deflection/separation in m, force in N, InVOLS in m/V,
  spring constant in N/m, work in J, direction in rad;
- sign conventions: separation = height - deflection; positive deflection =
  cantilever bending toward the sample; increasing-right/up data follows the
  frozen contact conventions;
- calibration: raw_v -> deflection_m (x InVOLS) -> force_n (x k); double
  calibration rejected; missing calibration raises MISSING_CALIBRATION;
- contact: threshold (k*sigma with persistence 3), ratio of variances
  (Gavara 2016), piecewise (value-continuous baseline/contact), ensemble
  (median of valid candidates, explicit disagreement, optional deterministic
  bootstrap);
- work: force integrated over tip-sample separation on the common overlap
  domain, monotone interpolation, trapezoidal arithmetic;
- QC: typed failure reasons beside a summary score (MISSING_CALIBRATION,
  INVALID_CALIBRATION, MISSING_APPROACH, MISSING_RETRACT, NONFINITE_DATA,
  NONMONOTONIC_COORDINATE, BASELINE_TOO_SHORT, BASELINE_UNSTABLE,
  CONTACT_NOT_FOUND, CONTACT_METHOD_DISAGREEMENT, SATURATED_SIGNAL,
  EVENT_NOT_FOUND, INSUFFICIENT_OVERLAP, FIT_NOT_ELIGIBLE).

External reference profile:

- nanite 4.2.3 (GPL-3; subprocess boundary only, never imported by SPMKit),
  afmformats 0.18.7 (MIT), Python 3.12.13, x86-64/glibc;
- frozen pipeline: compute_tip_position -> correct_split_approach_retract ->
  correct_tip_offset -> correct_force_offset -> correct_force_slope;
- frozen contact methods: deviation_from_baseline, fit_constant_line,
  fit_line_polynomial, fit_constant_polynomial;
- external outputs are NANITE_EXTERNAL_REFERENCE evidence only; they are
  canonical for no native ROV/ensemble/event/work/QC contract.

Maturity per capability (reconciled at independent audit):

- CROSS_VALIDATED (frozen nanite 4.2.3 profile only):
  compute_tip_sample_separation (tip-position convention verified on all 17
  retained cases, rtol 1e-9);
- NUMERICALLY_VERIFIED (defined numerical truth on deterministic phantoms
  and analytical oracles):
  identify_force_segments, calibrate_force_curve, fit_force_baseline,
  correct_force_baseline, contact_point_threshold,
  contact_point_ratio_of_variances, contact_point_piecewise,
  extract_force_events, integrate_force_work (integrator level only);
  the threshold method agrees with nanite deviation_from_baseline on clean
  flat-baseline cases (0..2 samples) but diverges on sloped/noisy baselines
  (up to 13 samples on the persisted 17-case matrix) and is NOT
  cross-validated as equivalent;
- SOFTWARE_VERIFIED (designed heuristics without unique numerical truth):
  contact_point_ensemble (median of valid candidates), the aggregate
  score_force_curve_quality summary score, prepare_force_curve
  (orchestration bounded by its weakest material component);
- no PHYSICALLY_VALIDATED claim.

Work integration is reported at three separated levels:

A. numerical integrator: exact-force/exact-coordinate/exact-domain recovery
   against closed-form truth at floating-point precision;
B. contact-conditioned work: the propagated contact-index error is reported
   separately from the integrator error;
C. full prepared pipeline: total end-to-end error reported as such, never
   attributed to the integrator.

The redistributable spectroscopy.nid case is a REAL_DATA_FAILURE_HANDLING_
WITNESS only: all 100 curves either complete or raise typed failures (99
NONMONOTONIC_COORDINATE, 1 INSUFFICIENT_OVERLAP, 0 silent).  It is not a
successful real-data end-to-end scientific proof and not physical validation.

The aggregate QC summary score is a designed heuristic (0..1 pass fraction);
it is not an externally validated scientific quality probability.

Known limitations:

- contact methods disagree on real data; the ensemble reports the
  disagreement rather than choosing silently;
- saturation detection requires an exact clipping plateau (baseline
  correction destroys it; score on the calibrated curve);
- real JPK/NID tip-sample separation is often non-monotone (snap-in/pull-off
  motion); work over tip position then raises the typed
  NONMONOTONIC_COORDINATE failure instead of fabricating a value.

Non-claims: no certified cantilever calibration; no universal JPK/ANA
numerical parity; no physical validation; no universal contact point; no
claim that baseline slope correction is always scientifically valid; no
automatic choice of the "correct" contact method; no uncertainty guarantee
from method spread alone; no model validity inference; no cell/material
property truth claim; no experimental reproducibility claim; no complete
force-map parity; no SMFS or viscoelastic parity from this batch.

## Force-spectroscopy mechanics (FS-F2)

The FS-F2 batch builds the indentation and contact-mechanics layer on the
FS-F1 preparation: indentation, fit windows, five frozen contact models
(hertz sphere, sneddon cone, flat punch, DMT, JKR), AICc model comparison,
sensitivity multiverse, residual bootstrap, diagnostics and force-volume
mapping.  13 public capabilities (compute_indentation,
select_contact_fit_window, forward_model, fit_hertz_sphere,
fit_sneddon_cone, fit_flat_punch, fit_dmt, fit_jkr, compare_contact_models,
analyze_force_fit_sensitivity, bootstrap_force_fit, diagnose_force_fit,
fit_force_volume_mechanics) with typed errors, immutable results and
explicit provenance.

- indentation convention: indentation = separation - contact_coordinate on
  the approach branch; the contact coordinate is the height at the contact
  index (deflection is zero there), so indentation equals the piezo motion
  past the contact minus the cantilever deflection; zero at the contact,
  positive into the sample in the indentation regime; pre-contact samples
  are excluded by the valid mask (never fabricated);
- phantom geometry: the separation is the increasing trace axis (FS-F1
  convention); height = separation + force/k stays strictly monotone
  because the deflection grows slower than the piezo motion in the
  indentation regime; clean phantoms carry zero pre-contact force, which is
  the exact frozen model behavior (the models have no long-range branch;
  the adhesion jump at the contact is preserved) and prevents the FS-F1
  baseline correction from subtracting model signal; the profile is a
  contact-branch-only representation of the frozen models and makes no
  claim about complete adhesive force curves with long-range interaction;
- frozen equations (reduced modulus E* = E/(1-nu^2)): hertz
  F = (4/3) E* sqrt(R) d^1.5; sneddon F = (2 tan(alpha)/pi) E* d^2; flat
  punch F = 2 E* R d; dmt F = hertz - F_adh; jkr loading branch via the
  parametric contact radius (monotone for a >= a0, range derived from the
  data, w = 0 reduces to hertz);
- fits: nonlinear least squares of E (and F_adh / w) over the contact fit
  window with geometry parameters fixed; results carry parameters,
  covariance, residuals, rmse and AIC/AICc/BIC;
- comparison: AICc weights over the identical data subset; the recommended
  model is the AICc minimum unless the runner-up retains considerable
  support (Delta AICc < 4 -> ambiguous); the comparison is model-relative
  and never a physical-truth claim;
- reliability: deterministic sensitivity multiverse over contact offsets
  and fit-window lower-bound fractions (<= 512 configurations) with
  one-at-a-time contact and window sensitivity indices relative to the
  baseline configuration and a dominant-sensitivity classification
  (contact / window / none, relative index > 20%); deterministic
  residual/block-residual bootstrap with percentile intervals; the
  diagnostic summary status is a policy (ok/review), never a probability.

Recovery bounds (clean phantoms, FS-F1 ensemble contact):

- hertz family (hertz sphere, sneddon cone, flat punch): E within 5%
  (residual bias is the contact precision, ~1 sample = 1.5e-8 m); with
  noise (sigma = 2e-12 N) within 10%; small force offset + residual slope
  within 5%;
- adhesive models (DMT, JKR) with windows trimmed past the snap-in region:
  DMT E within 30% and F_adh within 1.5e-9 N; JKR E within 20% and w within
  30%; the FS-F1 contact ensemble is unstable on snap-in curves (up to ~10
  samples off); dedicated snap-in contact detection is future work.

Maturity per capability (reconciled at independent audit):

- NUMERICALLY_VERIFIED (defined numerical truth on deterministic phantoms,
  independent analytical oracle and the frozen nanite contact campaign):
  compute_indentation, forward_model, fit_hertz_sphere, fit_sneddon_cone,
  fit_flat_punch, fit_dmt, fit_jkr, compare_contact_models (arithmetic),
  bootstrap_force_fit (resampling arithmetic), fit_force_volume_mechanics;
- SOFTWARE_VERIFIED (designed heuristics and policies without unique
  numerical truth): select_contact_fit_window (window policy),
  analyze_force_fit_sensitivity (multiverse interpretation),
  diagnose_force_fit (summary policy), and the model-recommendation
  policy inside compare_contact_models (Delta AICc < 4 threshold);
- external overlap: the FS-F1 contact ensemble lies inside the nanite
  4-method contact bracket on all 16 prepared P-cases of the frozen
  black-box campaign (NANITE_EXTERNAL_REFERENCE evidence; canonical for no
  native fit contract);
- no PHYSICALLY_VALIDATED claim.

Failure witnesses (typed, never silent):

- M11 saturated curve: SATURATED_SIGNAL flagged by the FS-F1 quality gate;
  the fitted modulus leaves the clean recovery band (bias reported);
- M15 cone data under a hertz hypothesis: the model comparison prefers
  sneddon_cone with weight > 0.9;
- M17 shallow noisy indentation and M18 flat curve: preparation raises the
  typed CONTACT_NOT_FOUND failure;
- real-data witness (redistributable spectroscopy.nid): every curve either
  completes the FS-F2 stack or raises a typed failure; a successful fit is
  required to be finite; no silent NaN-filled success is allowed.

Non-claims: no external mechanical-fit parity (nanite contact campaign is
contact-only); no snap-in contact detection; no free contact-offset fit
parameter; no uncertainty-calibrated intervals (bootstrap percentiles are
point-estimate spread, not coverage-guaranteed); no tip-radius
identifiability (R is fixed, never fitted); no adhesion-hysteresis or
pull-off model; no rate/viscoelastic dependence; no physical validation; no
experimental reproducibility claim.

## Force-spectroscopy viscoelasticity (FS-F3)

The FS-F3 batch adds a validated time-domain viscoelastic layer on the
FS-F1/FS-F2 stack: temporal protocol identification, indentation rates,
stress-relaxation and creep extraction, five lumped response models
(Kelvin-Voigt, Maxwell, standard linear solid, generalized Maxwell/Prony,
power law), the spherical hereditary-integral models (Lee-Radok loading and
Ting loading/unloading with contact-time memory), AICc model comparison,
sensitivity multiverse, force-volume mapping.  14 public capabilities with
typed errors, immutable results and explicit provenance.

- temporal contract: time in seconds, strictly increasing per segment,
  duplicates raise DUPLICATE_TIMESTAMPS, nonuniform sampling allowed
  (never resampled), no assumed acquisition rate; a missing time axis
  raises MISSING_TIME (a reconstructed clock requires an explicit
  assume_uniform_rate); the instrument clock is segment.time;
- reader limitation (explicit): the JPK and NID readers do NOT populate
  ForceSegment.time, so no automatic general JPK/NID time-domain
  viscoelastic analysis is claimed; FS-F3 is usable when an explicit valid
  time axis is present or reconstructed by an explicitly requested
  known-rate policy (assume_uniform_rate); reader timing extraction is a
  separate future batch;
- protocol classes: LOADING_RAMP, UNLOADING_RAMP, DISPLACEMENT_HOLD,
  FORCE_HOLD, CREEP, STRESS_RELAXATION, TRIANGULAR_LOADING,
  INSUFFICIENT_PROTOCOL, AMBIGUOUS_PROTOCOL; identification is rate-region
  based (median-of-nonzero-rate thresholds); trusted instrument labels in
  curve.metadata take precedence; a displacement hold with a decaying force
  is STRESS_RELAXATION, a force hold with a drifting displacement is CREEP;
- phantoms: the force traces derive from the independent oracles; the
  piezo position is the clean position while noise lives on the force
  channel only (the derived separation then jitters inside the FS-F1
  work-integral tolerance); the response models are exact in the hold
  region; ramp segments are elastic-following placeholders (documented);
- frozen lumped equations: KV creep J(t) = (1/E)(1 - exp(-t/tau)),
  tau = eta/E; Maxwell E(t) = E exp(-t/tau); SLS
  E(t) = E_inf + (E0 - E_inf) exp(-t/tau_relax) with the creep form
  J(t) = J_inf - (J_inf - J0) exp(-t/tau_retard) and the conversions
  J0 = 1/E0, J_inf = 1/E_inf, tau_retard = tau_relax * E0/E_inf; Prony
  E(t) = E_inf + sum E_i exp(-t/tau_i) with E_i >= 0, tau_i > 0, strictly
  increasing tau (duplicates rejected typed) and no uniqueness claim;
  power law E(t) = E_ref (t/t_ref)^(-alpha), 0 < alpha < 1, t = 0 excluded;
- frozen hereditary integrals (sphere, reduced modulus):
  Lee-Radok F(t) = c int_0^t E(t - t') d/dt' delta(t')^1.5 dt' with the
  monotonic-contact-radius condition (LEE_RADOK_NONMONOTONIC typed);
  Ting adds the unloading branch F(t) = c int_0^{t1(t)} ... with
  delta(t1(t)) = delta(t) on the loading branch (contact-time memory;
  TING_HISTORY_UNAVAILABLE typed when the history cannot be
  reconstructed); the production quadrature is the first-order
  Riemann-sum-in-increments rule with right-edge modulus evaluation;
  the independent oracle uses a 16-substep midpoint rule (agreement
  0.5-0.7%);
- fits: shared deterministic least-squares engine with an explicit
  multi-start (flat-valley protection) and a normalized objective;
  SLS-constrained parameterizations (a = (E0 - E_inf)/E0, creep
  increments) keep the model domains valid; Lee-Radok and Ting fit the
  SLS relaxation modulus through the integral (recovery within ~40%
  E0/E_inf and ~50% tau on clean phantoms; the loading curve carries less
  information than a hold); the creep absolute compliance level is
  contact-coordinate limited (~20% of the J0 scale) so the creep recovery
  is reported on the compliance INCREMENT (dJ, tau_retard) plus the
  absolute level with a wide honest bound;
- comparison: AICc over identical observations with the finite-sample
  correction, Delta AICc < 4 ambiguity, model-relative weights only;
- sensitivity: deterministic multiverse over contact offsets, hold-boundary
  offsets and equilibrium-tail fractions with one-at-a-time indices
  (contact/boundary/window) and a dominant classification (contact /
  boundary / window / none at the 20% threshold); raw configurations and
  failures exposed;
- volume: per-curve identify -> prepare -> extract -> SLS mapping with
  modulus/viscosity/relaxation-time maps, model/ambiguity/sensitivity
  maps and an explicit failed mask (nothing silently dropped).

Maturity per capability (reconciled at independent audit):

- NUMERICALLY_VERIFIED (defined numerical truth on deterministic phantoms
  and the independent analytical/hereditary oracles): indentation rate,
  relaxation/creep extraction, the five lumped forward models and fits,
  Lee-Radok (within the accurately demonstrated scope: forward parity
  0.7%, inverse bounds documented), Ting (independent history validation),
  force-volume mapping;
- SOFTWARE_VERIFIED (designed policies inseparable from the public
  results): protocol identification (the rate-region arithmetic is
  numerically verified but the protocol-type decision and the ambiguity
  policy are designed), the model comparison (the AICc arithmetic is
  numerically verified but the recommendation policy is part of the
  result), the sensitivity analysis (the arithmetic is numerically
  verified but the dominant-source interpretation is policy);
- external: pyvisco 2.1.3 (BSD-3) is a frozen COMPATIBILITY WITNESS only:
  the fixed-tau-grid NNLS reconstruction and the production free-tau fit
  both reproduce the same synthetic normalized modulus within 0.10 on the
  shared grid; no parameter equality and no CROSS_VALIDATED record;
- no PHYSICALLY_VALIDATED claim.

FS-F1 compatibility repair (proven defect, bounded): the piecewise contact
method's polyfit crashed with an untyped LinAlgError on constant-coordinate
windows (e.g. a flat hold); the candidate is now rejected (returns inf)
with a rank-deficiency guard, never an untyped crash.

Non-claims: no universal linear-viscoelastic validity; no physical
validation; no unique Prony spectrum and no universal number of relaxation
modes; no guaranteed equilibrium from a finite dwell; no automatic correct
model; no complete systematic uncertainty; no frequency-domain
microrheology; no active oscillatory rheology; no SMFS/unfolding support;
no certified viscosity or modulus; no experimental cell/material truth;
synthetic map recovery is not experimental map validation.

## Single-molecule force spectroscopy (FS-F4)

The FS-F4 batch adds the SMFS stack on the FS-F1/FS-F2/FS-F3 foundations:
molecular extension with explicit zero policies, polymer fits (WLC, eWLC,
FJC, eFJC), model comparison, unfolding-event detection and quantification,
contour-length increments from independent fits, loading rates, Bell-Evans
and Dudko-Hummer-Szabo kinetics, force-clamp survival with right censoring,
population aggregation and batch orchestration.  16 public capabilities
with typed errors, immutable results and explicit provenance.

- molecular extension contract: extension = retract separation minus an
  explicit tether zero; supported reference policies: "offset" (physical
  offset, m), "index" (reference sample), "pre_event" (caller-supplied
  branch start), "estimator" (the retract zero-force crossing with its own
  diagnostics); the zero is never inferred silently from the contact;
- frozen polymer equations: WLC F = (k_BT/Lp)[1/(4(1-x/Lc)^2) - 1/4 + x/Lc]
  (never evaluated at or beyond the singularity); eWLC (implicit,
  Odijk-style, solved per point by brentq with a force-scale xtol; S -> inf
  reduces to the WLC); FJC x/Lc = coth(y) - 1/y with y = F b/k_BT (stable
  Langevin); eFJC x/Lc = L(y) + F/Sk (Sk -> inf reduces to the FJC); the
  WLC/FJC fits use separable closed-form structures (1-D searches over the
  nonlinear parameter) to avoid the flat (Lc, Lp) and (Lc, b) valleys;
- event detection is a documented heuristic (SOFTWARE_VERIFIED): sustained
  force drops on the pull-ordered retract branch with public thresholds;
  rejected candidates retained with reasons; the final detachment is
  distinguished from internal unfolding (post-drop baseline return);
  sub-threshold drops are not detected (typed NO_EVENTS);
- contour-length increments derive from independent pre/post WLC fits on
  the ABSOLUTE molecular extension (a branch-relative fit would absorb the
  event offset into a biased contour length);
- loading rates: the measured local slope of force vs time before each
  event (least squares + robust median-of-pairs); the theoretical rate
  (effective stiffness x pulling velocity) is reported separately, never
  substituted;
- Bell-Evans: the most-probable-force regression
  F* = (k_B T/x_beta) ln(r x_beta/(k0 k_B T)) is the primary estimator
  (the BE likelihood is degenerate toward x_beta -> 0, documented); the
  bounded likelihood runs as a secondary with an identifiability
  diagnosis; the survival convention is
  S(F) = exp(-k0 k_B T/(r x_beta)(exp(F x_beta/k_B T) - 1)) (the
  coefficient is dimensionless; an inverted convention was found and fixed
  in the production, the oracle and the generator);
- Dudko-Hummer-Szabo: frozen nu in {1/2, 2/3} (cusp / linear-cubic), the
  log-space rate evaluation with a consistent exp cap (a floating-point
  cancelation artifact in the near-boundary profile was found and fixed);
  the fitted energy landscape is not claimed to be physically unique;
- force clamp: Kaplan-Meier survival with right censoring (events before
  censors at ties; events leave the risk set); median lifetime typed
  UNDEFINED_MEDIAN when unreachable; the exponential rate is the
  censoring-aware MLE n_events/sum(times);
- population and batch: aggregation without molecular-identity claims;
  per-curve results and failures retained with reasons; deterministic
  ordering and replay.

Maturity per capability (reconciled for this batch):

- NUMERICALLY_VERIFIED: the four polymer fits and forward models (with
  parameter-specific evidence: the eWLC stretch modulus and the eFJC
  stretch scale are weakly identifiable from a single branch; the response
  reconstruction is verified and the parameter recovery bounds are
  documented), contour-length increments (delta-Lc within 10%; the delta is
  largely zero-translation invariant while the absolute contours carry the
  zero-policy error), event quantification, loading-rate arithmetic,
  Bell-Evans (F* regression; the likelihood degeneracy documented), DHS
  (response level with the domain-censoring identity verified; the
  landscape non-uniqueness documented), force-clamp survival arithmetic
  (Kaplan-Meier and the censored exponential-rate MLE verified against
  hand-derived cases);
- SOFTWARE_VERIFIED: compute_molecular_extension (the estimator reference
  policy is a heuristic inside the same callable), the SMFS fit-window
  policy, polymer-model recommendation, unfolding-event detection,
  population grouping, batch orchestration;
- external: no exact external polymer/kinetic profile exists; pyvisco was
  the FS-F3 witness and does not cover the SMFS models; no CROSS_VALIDATED
  and no PHYSICALLY_VALIDATED capability;
- legacy chain.py (the GUI-era WLC/FJC module) is untouched and
  unregistered; the FS-F4 models are the registered, oracle-validated
  implementations of the frozen conventions (Marko-Siggia default, explicit
  eWLC/eFJC stretch conventions).

Non-claims: no automatic molecular identity; no universal polymer model;
no certified contour length; no physical validation; no guaranteed single
tether; no guaranteed unfolding interpretation; no universal event
detector; no unique DHS energy landscape; no universal Bell-Evans validity;
no guaranteed independence of events; no complete kinetic uncertainty; no
hidden correction for linker or handle compliance; no experimental
protein-state truth; no steered-MD equivalence; no force-clamp validation
on a physical instrument; synthetic population recovery is not biological
validation.

## Test-count policy

The collection total is measured with:

```bash
python -m pytest --collect-only -q
```

The final `collected` value counts pytest test items after parametrization.
Skipped items remain collected; a parametrized test contributes one item per
parameter combination. The README does not duplicate this changing number.

## Claims not made

- no certified metrological traceability;
- no universal reader or instrument compatibility;
- no general equivalence with Gwyddion;
- no blind holdout for the Nanoscope campaign;
- no general `LEVEL 4` physical-validation claim;
- no `LEVEL 5` independent reproducibility claim;
- no endorsement by UTFSM, the SPM Lab, AFM-SPM, AFMReader, TopoStats, or Gwyddion.

When evidence is incomplete, the narrower statement governs.
