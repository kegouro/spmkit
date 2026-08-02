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

The concrete records are `.reference/gwyddion-2.71/source/modules/process/median-bg.c`,
`.reference/gwyddion-2.71/median-background-parity/median_background_behavior_probe.c`,
`.reference/gwyddion-2.71/median-background-parity/run_median_background_probe_campaign.sh`,
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

The records are `.reference/gwyddion-2.71/source/libprocess/filters-minmax.c`,
`/tmp/spmkit_flat_disc_probe_v3`, `/tmp/spmkit_flat_disc_reduction_trace_v1`,
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

## What remains open

- redistributable multi-instrument fixtures for built-in and adapter readers;
- independent comparisons for force spectroscopy, KPFM, spectral, and resonance workflows;
- a genuinely blind holdout campaign;
- calibrated physical references with explicit uncertainty;
- an independent reproduction of a frozen campaign.

SPM-Kit currently makes no general `LEVEL 4` or `LEVEL 5` claim.
