---
description: AFM, KPFM, force-spectroscopy, surface-metrology, resonance, software, and evidence terminology used by SPM-Kit.
---

# Glossary

## Instruments and signals

| Term | Meaning in this portal |
|---|---|
| **AFM** | Atomic force microscopy: scanning a tip-sample interaction while a feedback loop controls a measured observable. |
| **SPM** | Scanning probe microscopy, the broader family that includes AFM and KPFM. |
| **Cantilever** | Microfabricated elastic beam carrying the tip; its modal stiffness is $k$ (N m$^{-1}$). |
| **Deflection sensitivity / InVOLS** | Conversion from detector voltage to cantilever deflection, normally m V$^{-1}$. |
| **Feedback setpoint** | Target observable maintained by the controller; its physical meaning depends on the operating mode. |
| **Forward / backward scan** | Opposite fast-axis scan directions. Their difference can reveal lag, drift, and feedback artifacts. |
| **Optical lever** | Laser, cantilever, and segmented photodiode arrangement used to infer cantilever angle or deflection. |
| **Scanner** | Piezoelectric positioning system moving the tip or sample along calibrated axes. |
| **Topography** | Reconstructed feedback height channel, not a direct photograph of an unconvolved surface. |

## Force spectroscopy and mechanics

| Symbol or term | Definition and unit |
|---|---|
| $F$ | Normal force, N. |
| $d$ | Cantilever deflection, m. |
| $\delta$ | Sample indentation under the chosen contact convention, m. |
| $E$, $E^*$ | Sample Young's modulus and reduced modulus, Pa. |
| $\nu$ | Poisson ratio, dimensionless. |
| $R$ | Spherical or paraboloidal tip radius, m. |
| $\alpha$ | Conical tip half-angle, rad. |
| $a$ | Contact radius in an adhesive-contact model, m. |
| $w$ | Work of adhesion per area, J m$^{-2}$. |
| **Baseline** | Non-contact reference fitted and subtracted before segmentation or fitting. |
| **Contact point** | Estimated transition defining the indentation origin; a fitted quantity with uncertainty, not an observed truth. |
| **DMT** | Derjaguin-Muller-Toporov adhesive-contact regime; SPM-Kit exposes a declared spherical-plus-offset approximation. |
| **Hertz** | Non-adhesive elastic contact model used here for a spherical/paraboloidal tip. |
| **Hysteresis** | Difference between compatible approach and retract paths; integrated force-distance area has units J. |
| **JKR** | Johnson-Kendall-Roberts adhesive-contact model; SPM-Kit's route is experimental. |
| **Pull-off** | Detachment event; the negative minimum after baseline correction is used as an operational adhesion magnitude. |
| **Snap-in** | Sudden transition toward the surface when the attractive gradient overcomes the cantilever response. |
| **Sneddon** | Axisymmetric indentation solution used here for ideal conical contact. |

## Surface and electrical analysis

| Symbol or term | Definition and unit |
|---|---|
| **CPD**, $V_{\mathrm{CPD}}$ | Contact-potential difference, V; sign convention must be confirmed for the instrument. |
| $\phi$ | Work function, normally eV in KPFM reporting. |
| **KPFM** | Kelvin probe force microscopy, an electrical-feedback SPM mode mapping a CPD-related observable. |
| $S_a$ | Arithmetic mean absolute areal height deviation, same length unit as the height channel. |
| $S_q$ | Root-mean-square areal height deviation, length. |
| $S_z$ | Maximum areal height range under this implementation, length. |
| $S_{sk}$, $S_{ku}$ | Height-distribution skewness and kurtosis, dimensionless. |
| **Leveling** | Removing a declared reference form such as a plane or row offset. It changes reported statistics and low-frequency spectra. |
| **Mask** | Declared inclusion or exclusion set over a field. A mask changes the population being measured. |
| **Pixel pitch** | Lateral sample spacing, m pixel$^{-1}$, derived from range and grid dimensions. |

## Spectra and resonance

| Symbol or term | Definition and unit |
|---|---|
| **PSD** | Power spectral density; normalization and dimensional convention must accompany comparisons. |
| $q$ | Spatial frequency, m$^{-1}$ under the cycles-per-length convention used here. |
| $H$ | Hurst exponent of a declared self-affine fit, dimensionless. |
| $D$ | Surface fractal dimension inferred here as $3-H$, dimensionless and model-dependent. |
| $\xi$ | Correlation length estimate, m, under a declared estimator and threshold. |
| $f_0$ | Resonance frequency, Hz. |
| $Q$ | Quality factor, $f_0/\Delta f_{\mathrm{FWHM}}$, dimensionless. |
| $m_{\mathrm{eff}}$ | Effective modal mass under a one-mode oscillator model, kg. |
| **ASD** | Amplitude spectral density, commonly m Hz$^{-1/2}$ after calibration. |
| **Thermal tuning** | Estimating modal properties or stiffness from a calibrated thermal-noise spectrum. |
| **d² law** | Linear diameter-squared evaporation diagnostic, $d^2=d_0^2-Kt$, under diffusion-limited assumptions. |

## Software and evidence

| Term | Meaning |
|---|---|
| **Artifact contract** | Declared file, schema, units, hashes, and provenance passed between tools. |
| **Candidate dataset** | Located material requiring licensing, suitability, integrity, and campaign review; not automatically accepted evidence. |
| **Core** | Presentation-independent SPM-Kit numerical and I/O package. |
| **Fathom** | Interactive workspace that invokes public SPM-Kit Core paths. |
| **Level 1–5** | Claim-scoped evidence vocabulary from software verification through independent reproducibility; see [scientific status](../SCIENTIFIC_STATUS.md). |
| **Phantom** | Deterministic synthetic fixture with declared truth. It is not a physical reference. |
| **Provenance** | Source, version, parameters, units, transformations, environment, and checksums needed to inspect an artifact chain. |
| **System under test** | Installed public package or command invoked by a validation campaign without importing private internals. |

[:material-arrow-left: Implementation map](spmkit-workflows.md) ·
[:material-arrow-right: References](references.md)
