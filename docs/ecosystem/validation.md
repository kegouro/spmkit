# SPM-Kit Validation

<p align="center">
  <img src="../assets/ecosystem/validation-banner.png" alt="spmkit-validation banner" width="100%">
</p>

**External black-box validation harness.**

spmkit-validation runs SPM-Kit through `subprocess` — never importing its
Python code — and preserves reproducible evidence with frozen tolerances,
receipts, and canonical hashes.

## Campaigns

| Campaign | Measurands | Level | Status |
|---|---|---|---|
| Synthetic roughness v0.1 | Sa, Sq, Sz | <span class="level-badge level-3">LEVEL 3</span> | 18/18 PASS |
| Nanoscope SPM v0.1 | Matrices, Sa/Sq/Sz | <span class="level-badge level-2">LEVEL 2</span> | 18/18 within tolerance |
| Gwyddion roughness 48 v0.1 | Sa | <span class="level-badge level-1">LEVEL 1</span> | Reported |
| Real data roughness pilot v0.1 | Sa | <span class="level-badge level-1">LEVEL 1</span> | Reported |

## What it does not demonstrate

- No physical validation (LEVEL 4) or interlaboratory reproducibility (LEVEL 5)
- No blind holdout (Nanoscope had `ACCIDENTAL_PRE_FREEZE_UNBLINDING`)
- No universal equivalence with Gwyddion

## Links

- **Repository:** [github.com/kegouro/spmkit-validation](https://github.com/kegouro/spmkit-validation)
- **Canonical tag:** [gwyddion-cross-validation-v0.1](https://github.com/kegouro/spmkit-validation/releases/tag/gwyddion-cross-validation-v0.1)
- **Citation:** [CITATION.cff](https://github.com/kegouro/spmkit-validation/blob/main/CITATION.cff)

---

[:material-arrow-left: Data Hunter](data-hunter.md) · [:material-arrow-right: Pharos](pharos.md)
