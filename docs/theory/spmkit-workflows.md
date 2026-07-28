# SPM-Kit — from concept to software

Each theoretical idea has a concrete place in the application. SPM-Kit reads
NanoSurf (`.nid`, `.nhf`) and Gwyddion (`.gwy`) formats, and strictly separates
the analysis *core* from the interface. The GUI organizes work into
perspectives.

## Perspectives and theory

| Perspective | What it does | Theory it materializes |
|---|---|---|
| **Viewer** | topography, leveling, roughness, line profiles, KPFM | [Roughness/spectral](roughness.md) · [KPFM](kpfm.md) |
| **Nanomechanics** | Hertz/Sneddon fit, Young's modulus, adhesion, modulus maps | [Contact mechanics](contact-mechanics.md) · [F-d curves](force-distance.md) |
| **3D view** | 3D surface with hillshade illumination | [AFM principles](afm-principles.md) |
| **Resonance** | thermal tuning, mass sensing, evaporation, d² law | [Resonance & mass sensing](resonance.md) |
| **Simulator** | digital twin of the cantilever: thermal noise and mass shift | [Equipartition / m_eff](resonance.md) |
| **Figure editor** | publication figures: colormaps, scale bar, PNG/SVG/PDF export | result communication |
| **Compare** | merge 2–4 files with shared colorbar and scale | comparative analysis |

## Architecture

Three layers: `core/` (pure Python: io · analysis · viz), `cli/` and `gui/`.
The presentation only calls the core's public API. The `.nid` reading has
**machine-precision correlation** with Gwyddion: the theory relies on
trustworthy data.

!!! implementation "Core principle"

    All numerical analysis lives in `src/spmkit/core/`. The CLI and Fathom only
    orchestrate it — they never implement analysis or touch parsers directly.
    See [Architecture](../ARCHITECTURE.md) for module details.

---

[:material-arrow-left: Resonance & mass sensing](resonance.md) · [:material-arrow-right: Glossary](glossary.md)
