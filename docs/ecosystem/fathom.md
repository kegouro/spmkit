# Fathom

**Interactive scientific workspace built on SPM-Kit.**

Fathom is the PyQt6 desktop application that provides the visual workspace for
SPM-Kit. It is not a separate package — it ships as the `gui` extra
(`pip install spmkit[gui]`) and runs with `spmkit gui` or `make gui`.

## Perspectives

| Perspective | Function |
|---|---|
| **Viewer** | Topography, leveling, roughness, profiles, KPFM |
| **Nanomechanics** | Hertz/Sneddon fit, modulus maps, adhesion |
| **3D view** | Hillshade 3D surface rendering |
| **Resonance** | Thermal tuning, mass sensing, evaporation |
| **Simulator** | Cantilever digital twin |
| **Figure editor** | Publication figures (PNG/SVG/PDF) |
| **Compare** | Merge 2–4 files with shared scale |

## Design identity

Fathom uses the "Instrument" aesthetic: graphite + signal teal + contact gold.
The same tokens power the GUI, pyqtgraph, and matplotlib outputs. See
[BRAND.md](https://github.com/kegouro/spmkit/blob/main/docs/BRAND.md) for the
full design system.

## What Fathom is not

- Not a separate package from SPM-Kit
- Not a Gwyddion replacement
- Not a microscope controller
- Not certified metrology software

---

[:material-arrow-left: SPM-Kit](spmkit.md) · [:material-arrow-right: Phantoms](phantoms.md)
