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
| Nanoscope `.spm` pilot v0.1 | Six demonstrated files | 18/18 metric comparisons within tolerance | <span class="spm-level spm-level--2" data-level="2">NUMERICALLY_VERIFIED</span> limited parser claim | Partial support and `ACCIDENTAL_PRE_FREEZE_UNBLINDING` |

See [Scientific status](../scientific-status.md) for the complete mapping and
canonical evidence links.

## Traceability

The `.nid` path also provides byte-level inspection through `spmkit verify` and
`spmkit.core.trace_nid`. This checks declared byte budgets, dimensions, numeric
conversion, finiteness, and orientation rules. Integrity and parser traceability
do not establish physical correctness.

## What remains open

- redistributable multi-instrument fixtures for built-in and adapter readers;
- independent comparisons for force spectroscopy, KPFM, spectral, and resonance workflows;
- a genuinely blind holdout campaign;
- calibrated physical references with explicit uncertainty;
- an independent reproduction of a frozen campaign.

SPM-Kit currently makes no general `LEVEL 4` or `LEVEL 5` claim.
