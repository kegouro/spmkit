---
title: AFM/SPM theory
description: A practical theory path from instrument signal and force curves to roughness, spectra, KPFM, resonance, SPM-Kit implementation, and evidence.
---

# Theory: from signal to claim

This portal explains the physical models SPM-Kit implements, the assumptions
that make them usable and the evidence currently attached to each code path. It
is written for readers who want to understand what a parameter means before
clicking **Run**.

## Learning path

1. [AFM principles](afm-principles.md): tip, cantilever, optical lever, feedback, scanner, coordinates and calibration.
2. [Operating modes](operating-modes.md): contact, tapping, non-contact, force volume, quantitative imaging and KPFM context.
3. [Force-distance curves](force-distance.md): approach/retract, baseline, snap-in, contact, adhesion, hysteresis and segmentation.
4. [Contact mechanics](contact-mechanics.md): Hertz/paraboloid, Sneddon, DMT, JKR, reduced modulus and fit limits.
5. [KPFM](kpfm.md): contact-potential difference, work function, null feedback and sign conventions.
6. [Roughness and surface metrology](roughness.md): reference surface, leveling, Sa/Sq/Sz/Ssk/Sku, sampling and filters.
7. [Spectral and self-affine analysis](spectral-analysis.md): Fourier transform, radial PSD, Hurst exponent, fractal dimension and bandwidth.
8. [Resonance and mass sensing](resonance.md): SHO response, Q, thermal noise, effective mass and declared evaporation model.
9. [SPM-Kit implementation map](spmkit-workflows.md): module, Fathom perspective, CLI/API, evidence and limitation for each concept.
10. [Glossary](glossary.md) and [primary references](references.md).

## How to read an equation here

Every model is accompanied by:

- symbols and SI units;
- assumptions and common failure conditions;
- the current SPM-Kit code path and operating surface;
- the strongest retained evidence level for that path;
- a limitation that remains after the test passes.

An equation is not an endorsement for every sample. A fitted number is only as
defensible as the calibration, geometry, preprocessing, fit window and evidence
behind the path that produced it.

## Evidence vocabulary

`LEVEL 0 — CLAIMED` → `LEVEL 1 — SOFTWARE_VERIFIED` →
`LEVEL 2 — NUMERICALLY_VERIFIED` → `LEVEL 3 — CROSS_VALIDATED` →
`LEVEL 4 — PHYSICALLY_VALIDATED` → `LEVEL 5 — REPRODUCIBILITY_VALIDATED`.

The same project can contain Level 1, Level 2 and Level 3 capabilities at once.
No current public evidence supports a general Level 4 or Level 5 claim.

[:material-arrow-right: Begin with AFM principles](afm-principles.md)
