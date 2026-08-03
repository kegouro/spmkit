# Validation and verification

SPM-Kit uses three distinct evidence paths. They answer different questions and
must not be collapsed into a generic “validated” label.

## Internal software tests

Unit, integration, architecture, and GUI tests exercise executable behavior.
They cover readers, models, analysis, export, the CLI, and offscreen Fathom
workflows. Passing these tests is `LEVEL 1 — SOFTWARE_VERIFIED` for the tested
behavior, not evidence about every instrument or sample.

```bash
python -m pytest
```

## Numerical recovery

`tests/validation/test_recovery.py` constructs known numerical cases and checks
whether selected models recover the generating values inside their declared
tolerances. These tests support `LEVEL 2 — NUMERICALLY_VERIFIED` claims only for
the models, noise regimes, parameter ranges, and tolerances exercised there.

```bash
python -m pytest tests/validation/test_recovery.py -q
```

## External campaigns

The independent repository
[`spmkit-validation`](https://github.com/kegouro/spmkit-validation) invokes
SPM-Kit through public process interfaces and preserves campaign definitions,
references, tolerances, outputs, hashes, and limitations.

| Campaign | Scope | Result | Level | Limit |
|---|---|---:|---|---|
| Gwyddion roughness 48 v0.1 | Sa, Sq, Sz on 48 canonical synthetic matrices | 144/144 within tolerance | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> | No preprocessing; shared matrices; not physical validation |
| Real-data roughness pilot v0.1 | Sa, Sq, Sz on 12 public GWY matrices | 36/36 shared-matrix comparisons within tolerance | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> for the algorithm track | Parser/end-to-end observations are separate; real data are not ground truth |
| Gwyddion Revolve Arc 2.71 v1 | Data-adaptive arc-envelope background on a frozen asymmetric 5×7 field, six direction/inversion routes and focal kernel cases | 6/6 backgrounds and 5/5 valid corrected outputs within `5e-14`; horizontal-inverted reference defect preserved as evidence and repaired by reconstruction | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> for the frozen campaign | Gwyddion 2.71 only; radius in samples; known wrapper and one-sample reference defects documented; not physical validation or universal equivalence |
| Gwyddion Revolve Sphere 2.71 v1 | Data-adaptive sphere-envelope background on 10 logical pairs (20 normal runs per build) and 15 failing inverted runs; direct normal external reference and derived inverted background within 5e-14; safe inverted corrected reconstruction | 20/20 valid external runs and 10/10 derived inverted backgrounds within 5e-14 | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> for the frozen campaign | Gwyddion 2.71 only; radius in samples; 15/15 inverted wrapper crashes documented as reference failures; not physical validation or universal equivalence |
| Gwyddion Median Background 2.71 v1 | Local rank background on 36 frozen logical cases, 72 executions (36 normal, 36 ASan), radii 1/2/3/4/20/1024, and both direct/radixtree reference paths | Public background and corrected fields 36/36 bitwise exact; maximum absolute difference 0, maximum ULP 0, input mutation maximum 0, reconstruction maximum `4.4408920985006262e-16` | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen campaign | Gwyddion 2.71 only; finite inputs; no universal, performance, future-version, all-radii, or all-matrices claim; no public border/shape/rank configuration |
| Gwyddion Filter flat-disc morphology 2.71 v1 | 12 frozen fields, six sizes 2/3/4/5/30/31, full-field mask-ignore Opening and Closing | Kernels 30/30; Opening 72/72 and Closing 72/72 bitwise exact; max absolute difference 0, max ULP 0, signed-zero mismatches 0, input mutation 0 | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen campaign | Gwyddion 2.71 executable only; finite full-field data; no universal, NaN/Inf, ROI, mask, ASF, tip, physical rolling-ball, performance, other-build, public erosion/dilation, or source-only tie claim |
| Gwyddion Path Level 2.71 v1 | 18 frozen finite full-field families, ordered straight physical selections, thicknesses 1/2/3/128, 72 logical cases and 144 fresh external executions | Public arrays 72/72 bitwise exact, 4,652/4,652 elements exact; max absolute/ULP 0, signed-zero mismatches 0, 72/72 repeat pairs, normalized endpoints, and mutation/no-op classifications | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen campaign | Audited Gwyddion 2.71 Path Level executable only; no universal, NaN/Inf, ROI/mask, path/spline, profile, align-rows, volume, GUI, performance, other-build/version claim |
| Gwyddion Align Rows statistics 2.71 v1 | 64 finite cases, 16 each for Median, Median of differences, Trimmed mean, and Trimmed mean of differences; numeric masks, absent masks, both directions, and trims 0/0.05/0.5 | Portable source semantics: public 64/64 arrays and 3,888/3,888 elements bitwise exact. Installed fast-math profile: 61/64 arrays and 3,757/3,888 elements exact; only 3 signed-zero and 128 explained reassociation differences | <span class="spm-level spm-level--3" data-level="3">CROSS_VALIDATED</span> within the frozen dual-profile campaign | Finite frozen domain only; no universal, NaN/Inf, performance, other-version/build, GUI, adapter, or generic-`align_rows` compatibility claim |
| Nanoscope `.spm` pilot v0.1 | Six demonstrated files | 18/18 metric comparisons within tolerance | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> limited parser claim | Partial support and `ACCIDENTAL_PRE_FREEZE_UNBLINDING` |

See [Scientific status](../scientific-status.md) for the complete mapping and
canonical evidence links.

## Traceability

The `.nid` path also provides byte-level inspection through `spmkit verify` and
`spmkit.core.trace_nid`. This checks declared byte budgets, dimensions, numeric
conversion, finiteness, and orientation rules. Integrity and parser traceability
do not establish physical correctness.

### Gwyddion 2.71 Median Background

The frozen campaign trace is:

```text
Gwyddion source
→ external probe
→ independent Python oracle
→ frozen fixture
→ private SPMKit kernel
→ public API
→ public bitwise tests
→ scientific status
```

The concrete records are Gwyddion 2.71 source `modules/process/median-bg.c`,
the frozen `median_background_behavior_probe.c`,
and the frozen `run_median_background_probe_campaign.sh`,
`docs/design/GWYDDION_MEDIAN_BACKGROUND_COMPATIBILITY.md`,
`tests/validation/fixtures/gwyddion/median_background/median_background_reference.npz`,
`tests/validation/fixtures/gwyddion/median_background/median_background_reference.json`,
`src/spmkit/core/analysis/_median_background.py`,
`src/spmkit/core/analysis/background.py`,
`tests/core/test_gwyddion_median_background_private.py`,
`tests/core/test_gwyddion_median_background.py`,
`tests/validation/test_median_background_fixture_integrity.py`, and
`docs/scientific-status.md`.

The chain was frozen by `818dbd3` (evidence), `a53c3bb` (private kernel), and `ed5c837`
(public API). The permanent fixture contains canonical hashes; the original oracle and its
ephemeral source artifacts are identified in the fixture manifest. The campaign's runner
limitations are non-blocking: `|| true` does not preserve an original compiler exit, and the
auxiliary parser accepts broad `background_` and `corrected_` prefixes. Both binaries still
executed; 72 processes returned with empty stderr; normal/ASan stdout was byte-identical; and
the parsed outputs, oracle/reference equality, and canonical hashes were independently checked.

#### Focal test inventory

- Fixture integrity: 20 tests.
- Private Median Background: 67 tests.
- Public Median Background: 72 tests.
- Combined focal campaign: 442 tests.

These counts describe the frozen focal validation campaign for this capability. They are not
the global test total of the SPMKit project.

### Gwyddion 2.71 Filter flat-disc morphology

The frozen trace is:

```text
Gwyddion source
→ corrected external probe V3
→ executable reduction trace
→ independent oracle V2
→ frozen fixture
→ private SPMKit kernel
→ public bitwise tests
→ CROSS_VALIDATED status
```

The records are Gwyddion 2.71 source `libprocess/filters-minmax.c`,
the frozen `flat_disc_probe_v3` and `flat_disc_reduction_trace_v1`,
`docs/design/GWYDDION_FLAT_DISC_MORPHOLOGY_COMPATIBILITY.md`,
`tests/validation/fixtures/gwyddion/flat_disc_morphology/flat_disc_morphology_reference.npz`,
`tests/validation/fixtures/gwyddion/flat_disc_morphology/flat_disc_morphology_reference.json`,
`src/spmkit/core/analysis/_gwyddion_flat_disc_morphology.py`,
`src/spmkit/core/analysis/background.py`,
`tests/core/test_gwyddion_flat_disc_morphology_private.py`, and
`tests/core/test_gwyddion_flat_disc_morphology.py`.

The evidence commit is `2ba366e`; the private-kernel commit is `05c5ae4`. The claim is limited
to the 12 frozen fields and six sizes. Source strict ternaries and executable MINSD/MAXSD
equality behavior are distinguished; the rejected uninitialised-kernel probe is excluded, and
the corrected zero-initialised probe is the valid external evidence. No claim is made for
universal equivalence, non-finite data, ROI/masks, ASF, tip morphology, physical rolling-ball,
performance, other Gwyddion builds, public erosion/dilation, or source-only tie semantics.

### Gwyddion 2.71 Path Level

The frozen trace is:

```text
Gwyddion source
→ installed Path Level tool execution
→ frozen 72-case external probe
→ independent oracle V1
→ frozen repository fixture
→ private SPMKit kernel
→ public SPMChannel API
→ public bitwise tests
→ CROSS_VALIDATED status
```

The records are Gwyddion 2.71 source `modules/tools/pathlevel.c`,
the frozen `path_level_probe_v1` and independent `path_level_oracle_v1`,
`docs/design/GWYDDION_PATH_LEVEL_COMPATIBILITY.md`,
`tests/validation/fixtures/gwyddion/path_level/path_level_reference.npz`,
`tests/validation/fixtures/gwyddion/path_level/path_level_reference.json`,
`src/spmkit/core/analysis/_gwyddion_path_level.py`, `src/spmkit/core/analysis/leveling.py`,
`tests/core/test_gwyddion_path_level_private.py`, and
`tests/core/test_gwyddion_path_level.py`, and
`tests/validation/test_path_level_fixture_integrity.py`.

The evidence commit is `d3566ce`; the private-kernel commit is `4ead95b`. The claim is limited
to 18 finite, non-empty, full-field families, ordered straight selections, thicknesses 1, 2, 3,
and 128, 72 logical cases, 144 fresh executions, and 72/72 deterministic repeat pairs. Public
arrays are bitwise exact in 72/72 cases and 4,652/4,652 elements, with maximum absolute
difference 0, maximum ULP 0, signed-zero mismatches 0, normalized endpoints and mutation/no-op
classification 72/72, and input mutation 0. The audited module is Gwyddion 2.71 `tools.so`
with SHA-256 `4711c360dd42e3e16257bf0e86d8bd41852b43d1d34540bf097736a603146237` and Build ID
`600b16d9857946609b567704b406abcc74aea698`.

Gwyddion mutates its selected data field in place and publishes GUI undo/logging state; SPM-Kit
returns a new `SPMChannel`. No claim is made for universal equivalence, NaN/Inf, masks/ROI,
GwySelectionPath, splines/polylines, profiles, align-rows, volume line-leveling, GUI/undo/logging
or selection-widget parity, performance, or other Gwyddion versions or builds.

### Gwyddion 2.71 Align Rows statistics

The public validation trace is:

```text
Gwyddion source
→ installed external probe
→ independent portable V2 oracle
→ frozen dual-profile repository fixture
→ private SPMKit kernel
→ public SPMChannel wrappers
→ public bitwise tests
→ CROSS_VALIDATED status
```

The records are Gwyddion 2.71 source `modules/process/linematch.c`,
the frozen `align_rows_probe_v1` and independent `align_rows_oracle_stats_v2`,
`tests/validation/fixtures/gwyddion/align_rows_statistics/align_rows_statistics_reference.npz`,
`tests/validation/fixtures/gwyddion/align_rows_statistics/align_rows_statistics_reference.json`,
`docs/design/GWYDDION_ALIGN_ROWS_STATISTICS_COMPATIBILITY.md`,
`src/spmkit/core/analysis/_gwyddion_align_rows_statistics.py`,
`src/spmkit/core/analysis/leveling.py`,
`tests/core/test_gwyddion_align_rows_statistics_private.py`,
`tests/core/test_gwyddion_align_rows_statistics.py`, and
`tests/validation/test_gwyddion_align_rows_statistics_fixture_integrity.py`.

`portable_source_semantics` is the production contract.  Public output is bitwise exact to the
frozen V2 oracle for all `64/64` corrected arrays and `3888/3888` elements.  This is
`CROSS_VALIDATED` only in the frozen finite campaign: 16 cases per supported method, numeric and
absent masks, Exclude/Include/Ignore routing, horizontal/vertical orientation, and trim fractions
`0.0`, `0.05`, and `0.5`.  All eight requested background arrays (`504/504` elements) are bitwise
exact across profiles, and mutation/no-op classifications agree `64/64`.

The installed Gwyddion 2.71 `process.so`
(`c21d52375807ae096e34a3469c2f20c4c66ea3197479e13215a6d7b9d465b451`) is a secondary profile,
`installed_gwyddion_2_71_fast_math_profile`: public corrected arrays are bitwise exact in `61/64`
arrays and `3757/3888` elements.  The exact exception set is three signed-zero-only elements in
`median__plateaus_signed_zero__10`, and 64 finite elements each in
`median_of_differences__irregular__11` and
`trimmed_mean_of_differences__irregular__11`, bounded by maximum absolute difference
`5.329070518200751e-15`, with no NaN/Inf mismatch.  The installed-build diagnosis confirms GCC
16.1.1 `-ffast-math` associative reassociation with LTO; SPM-Kit deliberately preserves portable
source arithmetic rather than emulate that local build.  Therefore V3 is not justified.

No claim is made for non-finite fields, universal or performance equivalence, another Gwyddion
version/build, ROI/GUI/adapters, other Align Rows families, or the existing generic `align_rows`.

## What remains open

- redistributable multi-instrument fixtures for built-in and adapter readers;
- independent comparisons for force spectroscopy, KPFM, spectral, and resonance workflows;
- a genuinely blind holdout campaign;
- calibrated physical references with explicit uncertainty;
- an independent reproduction of a frozen campaign.

SPM-Kit currently makes no general `LEVEL 4` or `LEVEL 5` claim.
