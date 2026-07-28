# SPM-Kit

<p align="center">
  <img src="../images/brand/fathom_logo_light.png" alt="SPM-Kit" width="200">
</p>

**Numerical engine, Python API, CLI.**

SPM-Kit is the installable package (`pip install spmkit`) and the command-line
tool (`spmkit`). It contains all numerical analysis, file readers, and export
utilities. The CLI and Fathom are thin orchestration layers over the core API.

## What it does

- Reads `.nid`, `.nhf`, `.gwy`, `.spm` (partial), and experimental formats
- Computes ISO 25178 roughness, PSD, Hurst exponent
- Fits Hertz, DMT, JKR, WLC, FJC, SLS models
- Thermal tuning, mass sensing, evaporation analysis
- Force-volume maps, single-molecule event detection
- Reproducible pipelines (Recipe YAML), HTML/PDF reports, byte-level traceability

## Evidence

| Capability | Level |
|---|---|
| Physical models | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| Sa, Sq, Sz (synthetic) | <span class="level-badge level-3">LEVEL 3 CROSS_VALIDATED</span> |
| `.nid` round-trip | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |
| Experimental formats | <span class="level-badge level-exp">experimental</span> |

**486 unique automated tests.**

## Links

- **Repository:** [github.com/kegouro/spmkit](https://github.com/kegouro/spmkit)
- **Documentation:** this site
- **PyPI:** [pypi.org/project/spmkit](https://pypi.org/project/spmkit/)
- **Citation:** [CITATION.cff](https://github.com/kegouro/spmkit/blob/main/CITATION.cff)

---

[:material-arrow-left: Ecosystem overview](index.md) · [:material-arrow-right: Fathom](fathom.md)
