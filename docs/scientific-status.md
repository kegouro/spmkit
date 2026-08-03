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
- [Median Background Gwyddion 2.71 frozen manifest](../tests/validation/fixtures/gwyddion/median_background/median_background_reference.json)

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
.reference/gwyddion-2.71/source/modules/process/median-bg.c
  → .reference/gwyddion-2.71/median-background-parity/median_background_behavior_probe.c
  → .reference/gwyddion-2.71/median-background-parity/run_median_background_probe_campaign.sh
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
coverage; no reproduction of Gwyddion's internal radixtree; no performance-equivalence claim;
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
.reference/gwyddion-2.71/source/libprocess/filters-minmax.c
  → /tmp/spmkit_flat_disc_probe_v3
  → /tmp/spmkit_flat_disc_reduction_trace_v1
  → /tmp/spmkit_flat_disc_reduction_trace_v1/oracle_v2/flat_disc_morphology_oracle.py
  → tests/validation/fixtures/gwyddion/flat_disc_morphology/flat_disc_morphology_reference.npz
  → tests/validation/fixtures/gwyddion/flat_disc_morphology/flat_disc_morphology_reference.json
  → src/spmkit/core/analysis/_gwyddion_flat_disc_morphology.py
  → src/spmkit/core/analysis/background.py
  → tests/core/test_gwyddion_flat_disc_morphology_private.py
  → tests/core/test_gwyddion_flat_disc_morphology.py
  → docs/scientific-status.md
```

Evidence was frozen in `2ba366e`; the private kernel is `05c5ae4`. No public or documentation
commit is claimed here. **Non-claims:** no universal equivalence; no NaN or infinity coverage;
no ROI, masks, ASF, tip morphology, physical rolling-ball equivalence, performance parity,
other Gwyddion builds or versions, public erosion or dilation, or claim that source-level C
tie semantics alone reproduce the audited binary.

### Gwyddion 2.71 Path Level

**Claim:** `CROSS_VALIDATED` only within the frozen Path Level campaign against the audited
Gwyddion 2.71 tool `/usr/lib/gwyddion/modules/tool/tools.so`
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
.reference/gwyddion-2.71/source/modules/tools/pathlevel.c
  → installed Gwyddion 2.71 Path Level tool execution
  → /tmp/spmkit_path_level_probe_v1
  → /tmp/spmkit_path_level_oracle_v1
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
`/usr/lib/gwyddion/modules/process/process.so`
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
.reference/gwyddion-2.71/source/modules/process/linematch.c
  → /tmp/spmkit_align_rows_probe_v1
  → /tmp/spmkit_align_rows_oracle_stats_v2
  → tests/validation/fixtures/gwyddion/align_rows_statistics/
  → src/spmkit/core/analysis/_gwyddion_align_rows_statistics.py
  → src/spmkit/core/analysis/leveling.py
  → tests/core/test_gwyddion_align_rows_statistics.py
  → docs/design/GWYDDION_ALIGN_ROWS_STATISTICS_COMPATIBILITY.md
```

**Non-claims:** no universal equivalence; no NaN/Inf, other Gwyddion version or build, untested
matrix, performance, ROI/GUI, adapter, or other Align Rows method-family claim.  This finite
campaign does not establish physical validation or general SPMKit parity.

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
