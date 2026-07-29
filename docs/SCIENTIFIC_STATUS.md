# Scientific status

This page is the authoritative public map from SPM-Kit capabilities to the
evidence that currently supports them. It deliberately separates implementation,
software tests, numerical recovery, external comparison, and physical validation.

## Maturity vocabulary

| Level | Required meaning |
|---|---|
| `LEVEL 0 — CLAIMED` | A claim or intended behavior is documented, but executable evidence is not preserved. |
| `LEVEL 1 — SOFTWARE_VERIFIED` | The behavior is exercised by automated software tests. |
| `LEVEL 2 — NUMERICALLY_VERIFIED` | Known values are recovered within a stated numerical scope and tolerance. |
| `LEVEL 3 — CROSS_VALIDATED` | Results are compared with an external software or reference route under a frozen protocol. |
| `LEVEL 4 — PHYSICALLY_VALIDATED` | A physical reference or experiment supports the capability within a stated scope. |
| `LEVEL 5 — REPRODUCIBILITY_VALIDATED` | An independent party reproduced the result under the declared protocol. |

The level belongs to a particular claim, campaign, data family, metric, version,
and tolerance. It never transfers automatically to an adjacent feature.

## Capability matrix

| Capability | Implementation | Evidence | Level | Independent reference | Known limitation / next requirement |
|---|---|---|---|---|---|
| Sa, Sq, Sz on frozen synthetic matrices | `core.analysis.roughness` | 48 cases, 144/144 comparisons within `atol=1e-6 nm + rtol=1e-6` | `LEVEL 3 — CROSS_VALIDATED` | Gwyddion 2.71 library route through a frozen harness-authored wrapper | Shared matrices, no preprocessing, three metrics only; not physical validation or universal equivalence |
| Sa, Sq, Sz on public experimental GWY matrices | `core.analysis.roughness` | 12 cases, 36/36 shared-matrix comparisons within tolerance | `LEVEL 3 — CROSS_VALIDATED` for the shared-matrix algorithm track | Gwyddion 2.71 | Parser/end-to-end observations are separate: 10 equivalences and 2 preserved channel-count differences |
| Limited Nanoscope III `.spm` images | `core.io.bruker_spm` | Six demonstrated files; 18/18 Sa/Sq/Sz comparisons within tolerance and zero reported pixel delta | `LEVEL 2 — NUMERICALLY_VERIFIED` | Gwyddion 2.71 | `ACCIDENTAL_PRE_FREEZE_UNBLINDING`; partial variants only, no blind holdout or general Bruker support |
| NanoSurf `.nid` mapping and orientation | `core.io.nid`, `core.verify` | Synthetic byte-budget/orientation tests and selected lab-context comparisons | `LEVEL 1 — SOFTWARE_VERIFIED`; selected comparisons do not establish universal format coverage | Gwyddion exports for selected files | Private instrument corpus is not distributed; additional redistributable multi-instrument fixtures are needed |
| Hertz / conical contact and DMT paths | `core.analysis.forcecurve` | Unit and synthetic-recovery tests; Hertz/conical modulus recovery gates | `LEVEL 2 — NUMERICALLY_VERIFIED` within synthetic test scope | Analytical construction | No certified cantilever/tip calibration or broad experimental campaign |
| Adhesive JKR | `core.analysis.experimental` | Synthetic recovery of reduced modulus and work of adhesion; Hertz-limit test | `LEVEL 2 — NUMERICALLY_VERIFIED` within synthetic scope | Analytical construction | Experimental module; no physical-reference campaign |
| WLC and FJC chain models | `core.analysis.chain` | Analytical synthetic-recovery tests | `LEVEL 2 — NUMERICALLY_VERIFIED` within synthetic scope | Analytical construction | No cross-software or experimental population campaign |
| SLS relaxation | `core.analysis.experimental` | Synthetic recovery of characteristic time and elastic limit | `LEVEL 2 — NUMERICALLY_VERIFIED` within synthetic scope | Analytical construction | Loader/UI path for pause segments remains limited |
| Force-volume property maps | `core.analysis.forcevolume*` | Scalar/vectorized consistency and synthetic modulus-map recovery tests | `LEVEL 2 — NUMERICALLY_VERIFIED` within synthetic scope | Internal scalar and analytical controls | Not an independent reference; experimental calibration remains user supplied |
| KPFM / CPD | `core.analysis.kpfm` | Unit tests for CPD and work-function calculation | `LEVEL 1 — SOFTWARE_VERIFIED` | None | No public physical-reference campaign |
| PSD, correlation, fractal estimates | `core.analysis.spectral` | Unit and synthetic tests | `LEVEL 1 — SOFTWARE_VERIFIED` | None | Definitions and preprocessing must be matched before external comparison |
| Grain detection | `core.analysis.grains` | Synthetic morphology tests | `LEVEL 1 — SOFTWARE_VERIFIED` | None | Threshold-dependent; no universal segmentation benchmark |
| SHO resonance and thermal calibration utilities | `core.analysis.resonance`, `calibration` | Unit and numerical tests; limited experimental exercise is documented separately | `LEVEL 1 — SOFTWARE_VERIFIED`; no general physical claim | None for a frozen public campaign | Requires a redistributable calibrated reference and frozen acquisition context |
| Fathom workspace | `gui/` over public core APIs | Offscreen GUI tests plus architecture tests | `LEVEL 1 — SOFTWARE_VERIFIED` | None | Platform/Qt behavior can vary; GUI evidence does not upgrade numerical maturity |

## Canonical campaign records

- [48-case Gwyddion roughness summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/gwyddion_roughness_48_v0.1_summary.json)
- [Public experimental GWY pilot summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/real_data_roughness_pilot_v0.1_summary.json)
- [Nanoscope `.spm` pilot summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/nanoscope_spm_parser_pilot_v0.1_summary.json)
- [Nanoscope incident and final audit](https://github.com/kegouro/spmkit-validation/blob/main/docs/campaigns/nanoscope_spm_parser_pilot_v0.1_audit.md)

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
