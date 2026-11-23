# Fathom quick start

**SPM-Kit computes. Fathom lets the researcher inspect, configure and operate
those computations interactively.** Fathom is installed with SPM-Kit; it is not
a separate numerical package.

## First session

1. Install the GUI extra: `python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"`.
2. Launch `spmkit gui`, optionally followed by a file path.
3. Open a file with **Ctrl+O** or drag it onto the workspace.
4. Inspect the proposed routing. A mixed file may ask whether to open it as an image or force map.
5. Choose a perspective from the top bar or press **Ctrl+K** and search by name.
6. Configure the visible parameters. Record tip radius, fit model, leveling or thresholds when they affect the result.
7. Run the analysis and inspect the result, residuals, R² or other available quality indicators.
8. Export a figure/result/report as appropriate.
9. Save a `.spmproj` project with **Ctrl+S** when the workflow supports it.
10. Keep the source file, software version and exported provenance with the result.

## Which perspective?

| Intent | Display name in current code | Key |
|---|---|---|
| Topography, roughness and KPFM | Imagen | `image` |
| Particle segmentation | Granos | `grains` |
| PSD and self-affine analysis | Espectral | `spectral` |
| Cantilever spectrum | Sintonía térmica | `resonance` |
| Time-dependent resonance | Evaporación | `evaporation` |
| One force curve and contact fit | Curva de fuerza | `force` |
| Molecule-pulling events | SMFS | `smfs` |
| Force-volume properties | Mapa | `map` |
| Multiple files | Batch | `batch` |
| Publication output | Figura | `figure` |
| Surface rendering | Vista 3D | `view3d` |
| Educational cantilever simulation | Simulador | `simulator` |

Screenshots in this documentation are generated from deterministic synthetic
data by `scripts/gen_docs_media.py`; they are interface demonstrations, not
experimental validation.

[Open the complete Fathom tour](../ecosystem/fathom.md) ·
[Read the full manual](../user-guide.md)

## Force-map windows

In **Batch → Ventanas automáticas…**, select **Escalones de fuerza** or
**Contacto · Hertz esférico**, set the parameters, then choose the NID maps.
Select a result row to inspect the force trace against the acquisition index.
The shaded interval is inclusive. The vertical line marks the proposed step
boundary or the first post-contact sample. CSV exports include rows without a
measurement, sample indices starting at zero, source hashes, SI units in the
column names, parameters and the code revision when available.

- **Steps.** Select approach or retract, samples per side and noise multiplier.
  The selector screens consecutive force differences after removing a local
  slope. It measures isolated candidates by extrapolating two local lines to
  the same sensor height. It rejects close transitions and requires agreement
  with a shorter window. Slow transitions and unresolved neighbours can be
  missed. A candidate is a signal discontinuity, whose physical origin needs
  experimental controls.
- **Contact.** Enter the measured spherical tip radius, Poisson ratio and maximum
  fit depth. The mode uses the first 10% of approach as the pre-contact baseline,
  locates persistent repulsion, and refines the contact origin by a bounded Hertz
  fit. The final modulus uses only post-contact samples inside the specified
  depth. It requires a monotonic indentation coordinate, at least 12 fit samples,
  R² of 0.98 or greater, and agreement of the two half-window moduli within 25%
  of the full estimate. Check these assumptions for the material, probe and
  acquisition. Automatic selection and a good fit alone cannot establish
  that a liquid marble obeys spherical elastic contact mechanics. For the effect
  of contact location and fit depth on modulus estimates, see [Gavara (2016)](https://doi.org/10.1038/srep21267).

Use **Curva de fuerza → Ejes → Estilo de la curva…** for line widths and patterns,
axis stroke width, text size and axis titles. Display units follow the selected
physical quantity. **Ejes → Guardar vista del gráfico…** exports the visible
zoom, styles and residuals as vector SVG or PNG. Stroke and font preferences
persist locally. Axis aliases apply to the current acquisition.
