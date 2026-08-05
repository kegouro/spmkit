# SPM-Kit &middot; Fathom — Usage Guide

**Source manual `0.1.5.dev0` (Alpha) &mdash; GitHub release `0.1.4` &mdash; PyPI `0.1.2` &mdash; 2026-07-29**

---

*Canonical documentation: This Markdown file is the authoritative reference for the SPM‑Kit
development tree `0.1.5.dev0`. A printable companion PDF is available at
`docs/user-guide.pdf` and in the embedded [PDF reader](manual/reader.md). Both are verified
against the current source tree. The latest tagged source release is `0.1.4`; the latest
PyPI distribution is `0.1.2`.*

**Creator, author, and lead developer:** José Labarca Baeza.

Tomás Corrales and the SPM Lab at Universidad Técnica Federico Santa María provided selected experimental datasets and laboratory context during the development and evaluation of SPM-Kit.

María Saavedra Fredes and Benjamin Schleyer helped locate and share candidate datasets for the validation campaigns.

Released under the MIT license, without dedicated institutional funding.
**License:** MIT &bull; **Repository:** <https://github.com/kegouro/spmkit> &bull; **Site:** <https://kegouro.github.io/spmkit>

---

## 1. Introduction

### 1.1 What is SPM-Kit?

SPM‑Kit is an **open‑source Python toolkit for analysing AFM/KPFM scanning‑probe‑microscopy data**.
It reads demonstrated variants of NanoSurf `.nid` / `.nhf`, Gwyddion `.gwy`, Bruker/Nanoscope
`.spm`, and JPK force data, then exports inspectable results: roughness parameters, line profiles, KPFM contact‑potential
statistics, nanomechanical property maps, thermal‑tune cantilever calibration, grain detection,
spectral analysis, and single‑molecule force spectroscopy.

SPM‑Kit was created and is authored and led by **José Labarca Baeza** as an independent
software project. Acknowledged dataset and laboratory-context contributions do not create
software authorship or institutional ownership.

### 1.2 What is Fathom?

**Fathom** is the desktop workspace application bundled with SPM‑Kit. It is a PyQt6 + pyqtgraph
GUI organised into *perspectives* (task‑oriented views) rather than flat tabs. Each perspective
shows only the panels relevant to a specific workflow. A command palette (`Ctrl+K`) provides
keyboard access to everything.

### 1.3 Relationship between components

```
spmkit (Python package)
├── spmkit.core        — numerical engine (pure Python, no UI imports)
├── spmkit.cli         — command‑line interface (Typer + Rich)
└── spmkit.gui         — Fathom desktop workspace (PyQt6 + pyqtgraph)
```

- **`spmkit`** is the Python package and CLI entry point.
- **Fathom** is the graphical workspace. It imports `spmkit.core` for all computation; it never
  contains analysis logic itself.
- **SPM-Kit** is the project/ecosystem name.

### 1.4 What SPM-Kit does *not* do

- It is **not a microscope controller** (cannot connect to an instrument).
- It is **not a certified metrology tool**.
- It does **not** provide medical, clinical, or regulatory reports.
- It does **not** guarantee correctness for any specific instrument or sample.
- Its simulation features are **educational**, not quantitative digital twins.

### 1.5 Reproducibility

SPM‑Kit enforces strict separation between computation and presentation (verified by
`tests/test_architecture.py`). Analysis pipelines can be saved as YAML recipes (`core.pipeline`)
to preserve declared operations and parameters. Byte‑level tracing for demonstrated `.nid` paths is available through
`spmkit verify`.

### 1.6 Status

SPM‑Kit is **alpha‑stage** software (`Development Status :: 3 - Alpha`). Its strongest
retained evidence is `LEVEL 3 — CROSS_VALIDATED` for Sa, Sq, and Sz under frozen campaign
conditions: 48 synthetic matrices produced 144/144 conforming comparisons and 12 public
experimental GWY records produced 36/36 shared‑matrix comparisons against Gwyddion 2.71.
The parser/end‑to‑end observations remain separate. Six Nanoscope III `.spm` files support a
partial `LEVEL 2` claim with a documented pre‑freeze unblinding incident. KPFM, spectra,
grains, and resonance remain at Level 1; contact and chain models have claim‑scoped synthetic
Level 2 evidence. No general Level 4 or Level 5 claim is made. See
[§13](#13-scientific-validation-philosophy).

---

## 2. Installation

Requirements: **Python &ge; 3.11**.

| Distribution | Version documented on 2026-07-29 | Use when |
|---|---|---|
| PyPI | `0.1.2` | you need the published package snapshot |
| GitHub release | `0.1.4` | you need the latest tagged source release |
| `main` source tree | `0.1.5.dev0` | you need the behavior documented by this manual |

Choose the source explicitly. `pip install spmkit` currently installs the PyPI
snapshot, not the latest GitHub release.

### 2.1 Core only

```bash
python -m pip install "spmkit @ git+https://github.com/kegouro/spmkit@v0.1.4"
```

Installs the numerical core and CLI. Optional format dependencies are still required for
`.nhf`, `.gwy`, and adapter-backed formats.

### 2.2 GUI / Fathom

```bash
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@v0.1.4"
```

Adds: PyQt6, pyqtgraph, matplotlib, Crameri colormaps, matplotlib‑scalebar.

### 2.3 All features

```bash
python -m pip install "spmkit[all] @ git+https://github.com/kegouro/spmkit@v0.1.4"
```

`all` includes the declared reader, visualization, reporting, and GUI extras. It does not
include developer, GUI-test, parallel, or pandas extras.

### 2.4 Extras matrix

| Extra | Provides | Dependencies |
|-------|----------|-------------|
| `gui` | Fathom desktop workspace | PyQt6, pyqtgraph, matplotlib |
| `viz` | Publication figures, colormaps | matplotlib, cmcrameri, matplotlib‑scalebar |
| `gwy` | Gwyddion read/write (`.gwy`) | gwyfile |
| `hdf5` | HDF5 import/export | h5py |
| `grains` | Grain/particle detection | scipy |
| `report` | HTML/PDF report generation | Jinja2 + `spmkit[viz]` |
| `nanosurf` | Optional NSFopen dependency | NSFopen |
| `afm` | JPK QI, `.ibw`, HDF5, NT‑MDT, etc. | afmformats |
| `jpk` | JPK TIFF force curves | tifffile |
| `parallel` | Parallel force‑volume processing | joblib |
| `pandas` | DataFrame export for batch results | pandas |
| `dev` | Lint, test, type‑check | pytest, ruff, mypy, black |
| `test-gui` | GUI test runner | pytest‑qt |
| `docs` | Documentation build | mkdocs‑material |

### 2.5 Development installation

```bash
git clone https://github.com/kegouro/spmkit
cd spmkit
pip install -e ".[all,dev]"
```

### 2.6 Headless / HPC

For headless or cluster use, install the tagged core package only:

```bash
python -m pip install "spmkit @ git+https://github.com/kegouro/spmkit@v0.1.4"
```

All analysis code (`core.*`) has no GUI dependencies. For headless figure generation, add `viz`:

```bash
pip install "spmkit[viz]"
```

### 2.7 Platform notes

SPM‑Kit is developed and tested on **macOS** and **Linux**. Windows is not regularly tested.
GUI (Fathom) requires a Qt platform plugin. On headless servers, set `QT_QPA_PLATFORM=offscreen`
for tests; Fathom itself requires a display.

---

## 3. Verifying the installation

```bash
spmkit --version
# spmkit 0.1.4 for the tagged install above

python -c "import spmkit; print(spmkit.__version__)"
# 0.1.4 for the tag, 0.1.2 from PyPI, or 0.1.5.dev0 from main

python -c "from spmkit.gui.app import run; print('GUI import OK')"
# GUI import OK (does not launch; no Qt display needed)
```

---

## 4. Conceptual model

### 4.1 Architecture

```
                 ┌─────────────┐
 .nid / .nhf     │  spmkit.core│     .gwy, .h5, .csv, .json, .png, .pdf
 .gwy / .jpk ──► │  (pure Py)  │ ──►
                 └──────┬──────┘
                        │ public API
              ┌─────────┴─────────┐
              │                   │
         spmkit.cli          spmkit.gui
         (Typer+Rich)        (Fathom · PyQt6+pyqtgraph)
```

- `core` never imports from `cli` or `gui` (enforced by AST test).
- `cli` and `gui` import only the public API of `core`.
- All scientific logic lives in `core.analysis.*`.

### 4.2 Data model

```python
from spmkit import load, SPMData, SPMChannel

data: SPMData = load("scan.nid")
ch: SPMChannel = data["Z-Axis"]       # or data["Z-Axis", "forward"]

ch.data         # 2D ndarray in physical units
ch.unit         # "m", "V", "°", etc.
ch.x_range      # metres
ch.y_range      # metres
ch.shape        # (rows, cols)
ch.direction    # "forward" | "backward"
ch.metadata     # dict with instrument parameters
```

### 4.3 Force‑spectroscopy domain model

For force‑curve analysis, `spmkit.core.models.force` provides:

- **`ForceCurve`** — a single approach/retract cycle
- **`ForceSegment`** — a labelled segment (extend, retract, pause, modulation)
- **`ForceVolume`** — a grid of force curves (lazy‑loaded, not all held in RAM)
- **`Calibration`** — InvOLS, spring constant, method, temperature

### 4.4 Result objects

Every analysis function returns an immutable dataclass (e.g. `RoughnessResult`,
`CPDResult`, `GrainResult`, `FractalResult`, `IndentationResult`, `MechanicalMap`,
`VolumeResult`). Each has a `.to_dict()` method and can be serialised via
`spmkit.core.export`.

---

## 5. Supported file formats

| Extension | Source | Data type | Access | Extra | Status |
|-----------|--------|-----------|--------|-------|--------|
| `.nid` | NanoSurf classic | Images + spectroscopy | Read | — | Implemented; selected comparisons, synthetic byte/orientation tests; variants remain scoped |
| `.nhf` | NanoSurf HDF5 | Images | Read | `hdf5` | Experimental generic HDF5 traversal |
| `.gwy` | Gwyddion | Images | Read + Write | `gwy` | Implemented interoperability; no universal Gwyddion equivalence |
| `.spm` and detected numbered Nanoscope files | Bruker / Digital Instruments | Images | Read | — | Partial `LEVEL 2`; six demonstrated files; pre-freeze unblinding incident |
| `.jpk-force`, `.jpk` | JPK | Single force curve | Read | — | Implemented with synthetic fixtures; vendor variants remain scoped |
| JPK tagged TIFF | JPK export | Force data | Read | `jpk` | Experimental content-detected route |
| `.jpk-qi-data`, `.jpk-force-map`, `.jpk-qi-series` | JPK | Force data | Read | `afm` | Experimental adapter path |
| `.ibw`, `.h5`, `.tab` | afmformats-supported sources | Force data | Read | `afm` | Experimental adapter path; behavior follows installed afmformats |
| `.npz` | SPM-Kit Phantoms | Images | Read | — | Implemented for declared bundle keys, not generic NumPy archives |

### 5.1 Maturity vocabulary

| Label | Meaning |
|-------|---------|
| **LEVEL 0 — CLAIMED** | Intended behavior is documented without retained executable evidence. |
| **LEVEL 1 — SOFTWARE_VERIFIED** | Automated software tests exercise the declared path. |
| **LEVEL 2 — NUMERICALLY_VERIFIED** | A known value is recovered within a stated numerical scope and tolerance. |
| **LEVEL 3 — CROSS_VALIDATED** | A frozen external comparison supports a claim under declared versions, data, preprocessing, and tolerance. |
| **LEVEL 4 — PHYSICALLY_VALIDATED** | A calibrated physical reference supports the scoped capability. |
| **LEVEL 5 — REPRODUCIBILITY_VALIDATED** | An independent party reproduced the declared result. |

### 5.2 What "validated" means for `.nid`

The NanoSurf parser implements header-directed integer decoding, physical conversion, channel
ordering, and orientation. Synthetic byte-budget and orientation tests provide Level 1 evidence;
selected laboratory-context comparisons do not establish universal NanoSurf coverage. The
private instrument corpus is not distributed. Separately, the Sa/Sq/Sz shared-matrix campaigns
provide scoped Level 3 evidence. Keep parser, algorithm, and physical-validation claims separate;
see `docs/TRACEABILITY.md`, `docs/SCIENTIFIC_STATUS.md`, and SPM-Kit Validation.

---

## 6. Quick start

### 6.1 CLI: inspect a file

```bash
spmkit info scan.nid
```

### 6.2 CLI: roughness

```bash
spmkit roughness scan.nid -c Z-Axis --level plane
```

### 6.3 Python: load and analyse

```python
from spmkit import load
from spmkit.core.analysis import leveling, roughness

data = load("scan.nid")
flat = leveling.plane_fit(data["Z-Axis"])
stats = roughness.statistics(flat)
print(f"Sa = {stats.Sa:.3g} {stats.unit}")
```

### 6.4 Fathom: open a file

```bash
spmkit gui scan.nid
```

Then drag‑and‑drop a different file onto the window, or use `Ctrl+O`.

### 6.5 CLI: force curve

```bash
spmkit forcecurve curva.jpk-force --model dmt --tip-radius 2e-8
```

### 6.6 Export a publication figure

```bash
spmkit figure scan.nid -c Z-Axis -o topo.png --colormap tokyo
```

---

## 7. Fathom desktop workspace

### 7.1 Launching

```bash
spmkit gui                    # Fathom (default)
spmkit gui scan.nid           # open file on launch
spmkit gui --legacy           # legacy 7‑tab application (fallback)
```

### 7.2 Workspace layout

- **Top toolbar** — file actions (Open/Save) then perspective buttons.
- **Central area** — the main canvas for the active perspective.
- **Side docks** — inspector, navigator, pipeline, log panels (perspective‑dependent).
- **Command palette** — `Ctrl+K`; search or execute any command by name.
- **Status bar** — progress, errors, workspace state.

### 7.3 Opening data

- **Drag and drop** a file onto the window.
- **`Ctrl+O`** opens the file dialog.
- Fathom inspects the file and routes it: image channels go to image perspectives;
  force/spectroscopy data goes to force perspectives. If a file contains both images
  and curves, Fathom asks which to open.

### 7.4 Projects (`.spmproj`)

- **Save** (`Ctrl+S`) — persists the open file, pipeline parameters, and active perspective.
- **Open project** — restores the previous session state.
- File format: human‑editable YAML (`.spmproj`).

### 7.5 Reports

- **`Ctrl+Shift+R`** — generate a report (HTML + PDF) from the current data.
- For force‑volume data: `spmkit forcereport scan.nid -o report` generates a full
  report with property maps, statistics, and fitted curves.

### 7.6 Appearance

- **`Ctrl+Shift+L`** — toggle light/dark theme.
- **`Ctrl+Shift+A`** — appearance dialog with live preview. Choose from presets
  (Graphite, Paper, NanoSurf gold, Nord, Dracula, Solarized, Gruvbox), custom
  accent colour, and font size (Compact/Normal/Comfortable/Large).
- Settings persist between sessions.
- The theme feeds the application, pyqtgraph, and matplotlib simultaneously.

### 7.7 Command palette

Press `Ctrl+K`, type a command name, and press Enter. The palette indexes:

- "Go to &lt;Perspective&gt;" for every registered perspective
- "Theme: toggle light/dark" (`Ctrl+Shift+L`)
- "Customize appearance&hellip;" (`Ctrl+Shift+A`)
- Any commands registered by installed modules

### 7.8 Error reporting

Panel build failures show an error card inside the panel instead of crashing the
application. The **Log** panel (in Batch perspective) collects diagnostic messages.

---

## 7.9 Perspectives

### Image (`image`)
**Purpose:** Visualise and analyse 2D SPM image channels.

| Feature | Description |
|---------|-------------|
| Channel selector | Choose any loaded channel (Z‑Axis, Phase, CPD, etc.) |
| Leveling | Plane fit / polynomial / align‑rows; applied on selection |
| Colormap | Crameri or NanoSurf gold; switchable per channel |
| Line profile | Drag an ROI on the image to extract a 1D profile |
| Analysis panel | Roughness (Sa, Sq, Sz, Ssk, Sku), KPFM/CPD statistics, profile plot |
| Export | Profile CSV, figure PNG/SVG/PDF |

**Scientific assumptions:** Leveling plane‑fit preserves mean height and removes tilt.
KPFM work‑function calculation uses `Φ_sample = Φ_tip - e·CPD`.

### Grains (`grains`)
**Purpose:** Detect particles/grains on a levelled topography channel.

Uses SciPy, which is a required SPMKit dependency.

| Feature | Description |
|---------|-------------|
| Detection | Adaptive threshold (fraction of height range) + minimum size filter |
| Overlay | Colour‑coded grain overlay on the image |
| Statistics | Count, mean equivalent diameter, coverage fraction, density per &mu;m&sup2; |
| Controls | Minimum pixel size, relative height threshold |

**Limitations:** Simple threshold‑based watershed; not robust for overlapping or highly
irregular grains. No shape metrics beyond equivalent diameter.

### Spectral (`spectral`)
**Purpose:** Compute the radial power spectral density (PSD) and fractal parameters.

| Feature | Description |
|---------|-------------|
| PSD plot | Log‑log radial PSD |
| Fractal dimension | D = (7 &minus; &beta;) / 2 |
| Hurst exponent | H = 3 &minus; D |
| Correlation length | From PSD crossover |

**Scientific assumptions:** Self‑affine surface model. The fractal dimension is valid only
when the PSD is well approximated by a power law over the measured bandwidth.

### Thermal Tune (`resonance`)
**Purpose:** Fit a thermal noise spectrum to extract cantilever resonance parameters.

| Feature | Description |
|---------|-------------|
| SHO fit | Simple harmonic oscillator fit to the thermal spectrum |
| Outputs | Resonance frequency f&#x2080;, quality factor Q, spring constant k (by equipartition) |
| Input | A spectral channel loaded from a thermal‑tune measurement |

**Limitations:** Requires a clean thermal spectrum with a clear resonance peak.
Calibration accuracy depends on the quality of the thermal spectrum and the
equipartition assumption.

### Evaporation (`evaporation`)
**Purpose:** Mass sensing via evaporating droplet — track resonance frequency over time.

| Feature | Description |
|---------|-------------|
| Series | Load a folder of sequential thermal‑tune `.nid` files |
| Mass | Computed from frequency shift and cantilever calibration |
| Evaporation rate | dm/dt from mass vs. time |
| d&sup2; law | Linear fit of (radius)&sup2; vs. time; indicates diffusion‑limited evaporation |
| Outputs | Time series CSV, plots |

**Scientific assumptions:** Droplet mass is computed from `Δm = k / (4π²) · (1/f² - 1/f₀²)`.
The d&sup2; law fit assumes spherical droplet geometry. The evaporation rate is valid only
for diffusion‑limited regimes.

### Force Curve (`force`)
**Purpose:** Navigate, calibrate, and fit individual force‑distance curves.

| Feature | Description |
|---------|-------------|
| Curve navigation | `Ctrl+←` / `Ctrl+→` for previous/next curve |
| Calibration | InvOLS, spring constant (from metadata or manual) |
| Contact detection | Threshold or rate‑of‑variance (ROV) method |
| Contact models | sphere (Hertz), paraboloid (Sneddon), cone (Sneddon), DMT (Hertz + adhesion) |
| JKR | **Experimental** adhesive contact model |
| Monte Carlo | Optional uncertainty propagation for E and contact point |
| Outputs | Young's modulus ± 1&sigma;, R&sup2;, adhesion, dissipation, contact point |
| Export | Scientific CSV with fit curve, raw data, and units |
| Pipeline | Reproducible recipe (YAML) for calibration + contact + fit |

**Pipelines** are editable in‑app: every threshold, fit range, and model parameter is
exposed. The current pipeline can be saved/loaded as a YAML recipe.

### SMFS (`smfs`)
**Purpose:** Single‑molecule force spectroscopy — detect rupture events on retraction
curves and fit polymer chain models.

| Feature | Description |
|---------|-------------|
| Event detection | Peak‑prominence based (not a naive threshold) |
| Polymer models | WLC (Marko‑Siggia / Bouchiat) and FJC (Langevin) |
| Outputs | Contour length, persistence/Kuhn length per event; R&sup2; quality filter |
| Population | Contour‑length histogram across all events |
| Controls | R&sup2; threshold, prominence, height, temperature, WLC variant |
| Export | Events CSV |

**Limitations:** SMFS interpretation depends on the choice of polymer model and
temperature parameter. Prominence‑based detection may miss closely spaced or weak events.

### Map (`map`)
**Purpose:** Analyse a full force‑volume grid and generate property maps.

| Feature | Description |
|---------|-------------|
| Processing | Elasticity pipeline on every curve in the volume |
| Fast path | Vectorised (CPU) or GPU‑accelerated; used for uniform‑length curves |
| Pipeline path | Per‑curve pipeline; used for variable‑length curves (QI data) |
| Maps | Young's modulus, adhesion, contact point, R&sup2; — one 2D image each |
| Histogram | Distribution of each property |
| Export | Comprehensive CSV (metadata, per‑property statistics, per‑point table, no NaN dumps) |

**`--backend cpu` vs `--backend gpu`:** GPU backend requires CuPy (optional, not included
in any extra). CPU backend uses vectorised NumPy and is always available.

### Batch (`batch`)
**Purpose:** Process a folder of force curves (or maps) and produce a summary table.

| Feature | Description |
|---------|-------------|
| Input | Folder of `.jpk-force`, `.nid`, or other supported force files |
| Output | CSV with one row per file/curve; units in headers; empty cells for missing values |
| Pipeline | Same recipe used for all curves; can be customised |

### Figure (`figure`)
**Purpose:** WYSIWYG editor for publication‑quality figures.

| Feature | Description |
|---------|-------------|
| Layout | Title, axis labels, colour bar, scale bar |
| Colormap | All Crameri gradients + NanoSurf gold |
| Annotations | Draggable text annotations (fully customisable) |
| Scale bar | Physical‑unit scale bar (automatic or manual) |
| Export | PNG, SVG, PDF at publication resolution |

### 3D View (`view3d`)
**Purpose:** Interactive 3D surface rendering of topography.

| Feature | Description |
|---------|-------------|
| Surface | Hill‑shaded 3D mesh of the topography channel |
| Z exaggeration | Visual only; data values are unchanged |
| Rotation | Click and drag to rotate; scroll to zoom |
| Display | Z‑axis shown in nm/&mu;m for readability |

### Simulator (`simulator`)
**Purpose:** Educational cantilever digital twin.

| Feature | Description |
|---------|-------------|
| Model | Simple harmonic oscillator with thermal noise |
| Controls | Spring constant, quality factor, added mass |
| Visualisation | Thermal noise spectrum; resonance shift with added mass |

**Limitations:** Educational only. Does not account for nonlinearities, higher modes,
fluid damping, or real cantilever geometry.

---

## 8. End‑to‑end workflows

### 8.1 Topography leveling and roughness

**Goal:** Compute ISO 25178 areal roughness parameters from a scanned image.

| Step | GUI | CLI |
|------|-----|-----|
| Load | Drag &amp; drop `.nid` onto Fathom | `spmkit info scan.nid` |
| Level | Select channel, click Plane Fit | `--level plane` |
| Analyse | Read Sa, Sq, Sz from Analysis panel | `spmkit roughness scan.nid -c Z-Axis` |
| Export | Export figure via Figure perspective | `spmkit figure scan.nid -o topo.png` |

**Example data:** Synthetic data can be generated with:
```python
import numpy as np
# synthetic roughness demo
x = np.linspace(0, 5e-6, 256)
X, Y = np.meshgrid(x, x)
noise = np.random.normal(0, 1e-8, (256, 256))
topo = noise  # flat surface with Gaussian noise; Sq ≈ 1e-8 m
```

**Interpretation:** Sa is the arithmetic mean height; Sq is the RMS. Sz = Sp + Sv.
Ssk < 0 indicates valleys dominate; Ssk > 0 indicates peaks dominate. Sku > 3
indicates spiky surface; Sku < 3 indicates bumpy surface.

**Caveats:** Roughness depends on scan size, pixel density, and leveling method.
Always report these alongside roughness values.

### 8.2 Force‑curve contact mechanics

**Goal:** Fit a Hertz/DMT model to a single force‑distance curve and extract Young's modulus.

```bash
spmkit forcecurve sample.jpk-force --model dmt --tip-radius 2e-8
```
**Output** *(illustrative values; actual results depend on input data)***:**

```
          Force Curve Fit · curve 0 · dmt
┌───────────────────────┬───────────────────────┐
│ Parameter             │ Value                 │
├───────────────────────┼───────────────────────┤
│ Young's Modulus       │ 4.50 ± 0.08 MPa       │
│ R²                    │ 0.99921               │
│ Contact Point         │ 12.45 nm              │
│ Adhesion              │ 3.21 nN               │
│ RMSE                  │ 1.234e-11 N           │
│ Points Fitted         │ 214                   │
└───────────────────────┴───────────────────────┘
```

**GUI path:** Open file → Force Curve perspective → set model in Pipeline panel → inspect fit
on canvas → Export Curve CSV.

**Models:** `sphere` (Hertz), `paraboloid` (Sneddon paraboloid), `cone` (Sneddon cone),
`dmt` (Derjaguin‑Muller‑Toporov, Hertz + constant adhesion offset).

**Parameters:**

| Parameter | Typical range | Notes |
|-----------|--------------|-------|
| `--tip-radius` | 1–100 nm | Nominal tip radius from manufacturer or blind‑tip reconstruction |
| `--model` | sphere/dmt/paraboloid/cone | dmt is most common for soft samples |
| `--contact-method` | threshold/rov | `rov` is more robust to noise |

**Caveats:** Modulus values depend on tip radius (uncertain), contact model choice, and
calibration accuracy. Always report the tip radius, model, and fitting range. The JKR
model (`spmkit jkr`) is **experimental** — not validated against an independent reference.

### 8.3 Force‑volume property mapping

**Goal:** Process all curves in a force‑volume grid and generate property maps.

```bash
spmkit forcemap sample.nid --model dmt --fast --figure maps.png
```

**Output:** Maps of Young's modulus, adhesion, contact point, and R&sup2; — one 2D
image per property, plus a histogram.

**Fast vs Pipeline:** The `--fast` flag (default) uses vectorised computation; works
for uniform‑length curves. For variable‑length curves (QI data), use `--pipeline`.

**Parallel:** Add `--parallel` for multi‑core processing. Requires the `parallel` extra.

**Export everything:**

```bash
spmkit forceexport sample.nid -o ./results
```

Creates `results/` containing CSV maps, per‑curve table, summary statistics, and
an HTML + PDF report.

### 8.4 Thermal tune and cantilever calibration

**Goal:** Determine cantilever spring constant and resonance parameters.

**CLI path:**
```bash
# Process individual thermal spectrum (via Python API)
python -c "
from spmkit.core.analysis.mechanics import thermal_spring_constant
from spmkit.core.analysis.resonance import load_evaporation_series
# Load a series of thermal spectra
series = load_evaporation_series(sorted(Path('./tuning/').glob('*.nid')), spring_constant=0.3)
print(f'f0 = {series.bare_frequency:.1f} Hz')
print(f'k = {series.spring_constant:.3f} N/m')
"
```

**GUI path:** Open the first file of a tuning series → Thermal Tune perspective
(`resonance`) → inspect SHO fit and derived parameters.

**Caveats:** The equipartition method assumes the cantilever is a single‑mode SHO in
thermal equilibrium. Accuracy depends on bandwidth, sampling, and background noise.

### 8.5 Evaporation / mass sensing

**Goal:** Track mass loss of an evaporating droplet via cantilever resonance shift.

```bash
spmkit evaporation ./tuning_series/ -k 0.3 -o evap.csv
```

**Output CSV:** time (s), frequency (Hz), mass (kg), added mass (kg), evaporation
rate (kg/s). If d&sup2; law fitting succeeds, reports initial radius, lifetime, and
rate constant.

**Interpretation:** A linear d&sup2; vs. time trend indicates diffusion‑limited
evaporation (classic droplet model). Deviations may indicate pinning, environmental
changes, or non‑spherical geometry.

### 8.6 KPFM

**Goal:** Analyse contact potential difference (CPD) from a KPFM channel.

```bash
spmkit analyze scan.nid --tip-wf 4.8 -o ./results
```

**Output:** `results/scan_kpfm.csv` and `results/scan_kpfm.json` containing mean CPD,
standard deviation, min, max, and (if tip work function provided) sample work function.

**Formula:** &Phi;<sub>sample</sub> = &Phi;<sub>tip</sub> &minus; e &middot; CPD

**Caveats:** KPFM CPD values are relative to the tip. Absolute work function requires
tip calibration on a known reference sample (e.g. HOPG).

### 8.7 Grain analysis

```bash
spmkit grains scan.nid --min-size 10 --relative-height 0.5
```

**Output:** Number of grains, mean equivalent diameter, density, coverage fraction.

### 8.8 Spectral / fractal analysis

```bash
spmkit psd scan.nid -c Z-Axis
```

**Output:** Fractal dimension D, Hurst exponent H, PSD slope &beta;, R&sup2; of
log‑log fit, correlation length.

### 8.9 Batch processing

```bash
spmkit batch ./measurements/ -o summary.csv
spmkit fbatch ./curves/ -o force_batch.csv
```

### 8.10 Publication figure

```bash
spmkit figure scan.nid -c Z-Axis -o topo.svg --colormap batlow --title "AFM Topography"
```

---

## 9. Command‑line reference

### 9.1 Global options

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Print version and exit |
| `--help` | Show command help |

### 9.2 `spmkit info` — File metadata

```bash
spmkit info FILE
```

Displays a table of channels (name, direction, shape, unit, physical size).

### 9.3 `spmkit roughness` — ISO 25178 parameters

```bash
spmkit roughness FILE [-c CHANNEL] [-l LEVEL]
```

| Option | Default | Values |
|--------|---------|--------|
| `--channel`, `-c` | `Z-Axis` | Any channel name |
| `--level`, `-l` | `plane` | `plane`, `poly`, `none` |

**Output:** Sa, Sq, Sz, Ssk, Sku table via Rich.

### 9.4 `spmkit psd` — Spectral analysis

```bash
spmkit psd FILE [-c CHANNEL]
```

**Output:** Fractal dimension D, Hurst exponent H, PSD slope &beta;, R&sup2;, correlation
length.

### 9.5 `spmkit analyze` — Full pipeline

```bash
spmkit analyze FILE [-o DIR] [-c CHANNEL] [--cpd-channel CH] [--level L] [--tip-wf WF]
```

**Output:** `DIR/FILE_roughness.csv`, `DIR/FILE_roughness.json`, and KPFM equivalents
if a CPD channel is present.

### 9.6 `spmkit nanomech` — Single curve fit

```bash
spmkit nanomech FILE [-c CHANNEL] [--curve N] [--tip-radius R] [--model M] [--spring-constant K]
```

| Option | Default | Values |
|--------|---------|--------|
| `--channel`, `-c` | `Deflection` | Force channel |
| `--curve` | `-1` | Curve index (`-1` = centre) |
| `--tip-radius` | `1e-08` | Metres |
| `--model` | `sphere` | `sphere`, `paraboloid`, `cone`, `dmt` |
| `--contact-method` | `threshold` | `threshold`, `rov` |
| `--spring-constant` | — | N/m for indentation correction |

### 9.7 `spmkit grains` — Grain detection

```bash
spmkit grains FILE [-c CHANNEL] [-t THRESHOLD] [--min-size N] [--relative-height H]
```

### 9.8 `spmkit batch` — Batch image processing

```bash
spmkit batch FOLDER [-o CSV] [-c CHANNEL]
```

### 9.9 `spmkit evaporation` — Mass sensing

```bash
spmkit evaporation FOLDER [-k K] [-x POS] [-o CSV]
```

### 9.10 `spmkit figure` — Publication figure

```bash
spmkit figure FILE [-c CHANNEL] [-o PATH] [--colormap CMAP] [--title T]
```

| Option | Default | Notes |
|--------|---------|-------|
| `--output`, `-o` | `figure.png` | `.png`, `.svg`, or `.pdf` |
| `--colormap` | `batlow` | Any Crameri colormap or `gold` |

### 9.11 `spmkit convert` — Format conversion

```bash
spmkit convert INPUT OUTPUT
```

Converts `.nid` → `.gwy` (for opening in Gwyddion) or `.nid` → `.h5` (HDF5). Output
format is determined by extension.

### 9.12 `spmkit verify` — `.nid` integrity check

```bash
spmkit verify FILE
```

Performs up to eight structural and numeric integrity checks over the `.nid` header,
declared binary layout, channel ranges, and image axes. Malformed files can stop the
sequence early; exit code 1 is returned if any completed check fails.

### 9.13 `spmkit gui` — Launch Fathom

```bash
spmkit gui [FILE] [--legacy]
```

### 9.14 `spmkit workspace` — Force‑curve workspace

```bash
spmkit workspace [FILE]
```

Alternative force‑spectroscopy workspace (redesign). Requires `gui`.

### 9.15 `spmkit forcecurve` — Force curve fit

```bash
spmkit forcecurve FILE [--curve N] [--model M] [--tip-radius R]
```

### 9.16 `spmkit forcemap` — Force‑volume analysis

```bash
spmkit forcemap FILE [--model M] [--tip-radius R] [-o CSV] [-f PNG] [--fast|--pipeline] [--backend cpu|gpu] [--parallel]
```

### 9.17 `spmkit forcereport` — Force‑volume report

```bash
spmkit forcereport FILE [-o BASE] [--model M] [--tip-radius R] [--formats html,latex,pdf] [--backend cpu|gpu]
```

### 9.18 `spmkit forceexport` — Full export

```bash
spmkit forceexport FILE [-o DIR] [--model M] [--tip-radius R] [--backend cpu|gpu] [--no-report]
```

Exports CSV maps, per‑curve table, summary, and (optionally) HTML/PDF report.

### 9.19 `spmkit fbatch` — Batch force processing

```bash
spmkit fbatch FOLDER [-o CSV] [--model M] [--tip-radius R] [--parallel] [--recipe YAML]
```

### 9.20 `spmkit jkr` — Experimental JKR fit

```bash
spmkit jkr FILE [--curve N] [--tip-radius R] [--poisson V]
```

**&#x26a0;&#xfe0f; Experimental.** Not validated against an independent reference.
Do not use for publishable results without re‑validation.

---

## 10. Python API

### 10.1 Public imports

```python
from spmkit import load, SPMData, SPMChannel, __version__
from spmkit.core.analysis import leveling, roughness, kpfm, mechanics, profiles
from spmkit.core.analysis import spectral, grains, resonance, forcevolume, forcecurve
from spmkit.core.export import to_csv, to_json, to_hdf5
from spmkit.core.viz import FigureSpec, save_figure
```

### 10.2 Loading data

```python
from spmkit import load

data = load("scan.nid")      # NanoSurf classic
data = load("scan.nhf")      # NanoSurf HDF5
data = load("scan.gwy")      # Gwyddion

print(data.names)            # ['Z-Axis', 'Phase', 'CPD', ...]
channel = data["Z-Axis"]      # SPMChannel
```

### 10.3 Channel properties

```python
ch = data["Z-Axis"]
ch.data         # ndarray
ch.unit         # "m"
ch.x_range      # metres
ch.y_range      # metres
ch.shape        # (rows, cols)
ch.pixel_size_x # x_range / cols
ch.pixel_size_y # y_range / rows
```

### 10.4 Leveling

```python
from spmkit.core.analysis import leveling

flat = leveling.plane_fit(channel)
flat = leveling.polynomial(channel, order=2)
flat = leveling.align_rows(channel)
```

### 10.5 Roughness

```python
from spmkit.core.analysis import roughness

result = roughness.statistics(flat)
print(result.Sa, result.Sq, result.Sz, result.Ssk, result.Sku)
d = result.to_dict()
```

### 10.6 KPFM

```python
from spmkit.core.analysis import kpfm

result = kpfm.statistics(data["CPD"], tip_work_function=4.8)
print(result.mean, result.work_function)
```

### 10.7 Force spectroscopy

```python
from spmkit.core.analysis.mechanics import fit_hertz
from spmkit.core.io.forceload import load_nid_force

volume = load_nid_force("sample.nid")
curve = volume.curves[0]
result = fit_hertz(curve, tip_radius=10e-9, model="dmt")
print(result.young_modulus, result.r_squared, result.adhesion)
```

### 10.8 Force‑volume maps

```python
from spmkit.core.analysis.forcevolume import analyze_volume

result = analyze_volume(volume, model="dmt", parallel=True)
print(result.stats("young_modulus"))
emap = result.maps["young_modulus"]  # 2D ndarray
```

### 10.9 Spectral

```python
from spmkit.core.analysis.spectral import fractal_dimension, correlation_length

frac = fractal_dimension(flat)
print(frac.fractal_dimension, frac.hurst, frac.r_squared)
```

### 10.10 Grains

```python
from spmkit.core.analysis.grains import detect

result = detect(flat, min_size=4, relative_height=0.5)
print(result.n_grains, result.mean_diameter, result.density)
```

### 10.11 Export

```python
from spmkit.core.export import to_csv, to_json, to_hdf5

to_csv(roughness_result, "roughness.csv")
to_json(roughness_result, "roughness.json")
to_hdf5(data, "scan.h5")
```

### 10.12 Publication figures

```python
from spmkit.core.viz import FigureSpec, save_figure

spec = FigureSpec(title="AFM Topography", colormap="batlow")
save_figure(flat, spec, "topo.png")
```

### 10.13 Recipes

```python
from spmkit.core.pipeline import Recipe, Step, run

recipe = Recipe(steps=(
    Step(op="calibrate"),
    Step(op="find_contact_point"),
    Step(op="fit_elasticity", params={"model": "dmt", "tip_radius": 2e-8}),
))
_, ctx = run(recipe, curve)
print(ctx["young_modulus"], ctx["r_squared"])
```

---

## 11. Keyboard shortcuts

| Action | Shortcut | Context |
|--------|----------|---------|
| Command palette | `Ctrl+K` | Fathom (global) |
| Open file | `Ctrl+O` | Fathom |
| Save project | `Ctrl+S` | Fathom |
| Calculate map | `Ctrl+M` | Fathom |
| Generate report | `Ctrl+Shift+R` | Fathom |
| Toggle light/dark theme | `Ctrl+Shift+L` | Fathom (global) |
| Customize appearance | `Ctrl+Shift+A` | Fathom (global) |
| Export results (JSON) | `Ctrl+E` | Force‑curve workspace |
| Copy results | `Ctrl+Shift+C` | Force‑curve workspace |
| Pin current curve | `Ctrl+P` | Force‑curve workspace |
| Previous curve | `Ctrl+←` | Force Curve perspective |
| Next curve | `Ctrl+→` | Force Curve perspective |
| First curve | `Ctrl+Home` | Force‑curve workspace |
| Last curve | `Ctrl+End` | Force‑curve workspace |
| Switch tab 1–5 | `Ctrl+1`…`Ctrl+5` | Legacy app only |

All shortcuts use `Ctrl` (macOS: `⌘` is mapped to `Ctrl` by Qt).

---

## 12. Exports, provenance, and reproducibility

### 12.1 Export formats

| Format | Via | Notes |
|--------|-----|-------|
| CSV | `to_csv()`, CLI | Standard; units in headers |
| JSON | `to_json()`, CLI | Structured; suitable for programmatic consumption |
| HDF5 | `to_hdf5()` + `spmkit convert` | Self‑describing binary; requires `hdf5` extra |
| Gwyddion `.gwy` | `spmkit convert` | Round‑trip compatible with Gwyddion |
| PNG, SVG, PDF | `spmkit figure`, `save_figure()` | Publication‑quality figures |
| HTML + PDF | `spmkit forcereport` | Full force‑volume report |
| YAML recipe | `core.pipeline` | Reproducible analysis pipeline |

### 12.2 Units

All physical channels are stored in SI units (metres, Newtons, Volts, degrees).
Exported CSV/JSON files include unit annotations. `SPMChannel.unit` is always
present and should be checked before comparing values.

### 12.3 NaN behaviour

- Blank/unfitted regions in force‑volume maps are stored as NaN.
- Exported CSVs use empty cells for NaN (not the string "nan").
- Analysis functions propagate NaN to output; missing data is never silently
  filled with zeros.

### 12.4 Provenance

- `SPMData.source_path` records the original file path.
- `SPMData.metadata` preserves all instrument parameters from the file header.
- `.nid` files can be audited against their declared header and binary layout with
  `spmkit verify`.
- YAML recipes capture the exact pipeline parameters used.
- Export files include metadata when the format supports it (HDF5, JSON).

### 12.5 Round‑trip integrity

- `.nid` → `.gwy`: the current automated tests verify that the file is written and,
  separately, that representative in-memory GWY image data reload within numerical
  tolerance. They do not establish lossless round-trip fidelity for every `.nid` variant.
- `.nid` → `.h5`: the current automated tests verify that the exported HDF5 hierarchy
  is non-empty; full data-and-metadata round-trip equivalence is not yet claimed.
- CSV export is lossy (floating‑point formatting); use HDF5 for archival.

---

## 13. Scientific validation philosophy

Evidence belongs to a claim, data family, version, preprocessing path, tolerance,
and campaign. A high level for one metric never transfers automatically to an adjacent
reader, model, or sample.

### Evidence‑level vocabulary

| Level | Meaning |
|-------|---------|
| **LEVEL 0 — CLAIMED** | Intended behavior is documented without retained executable evidence. |
| **LEVEL 1 — SOFTWARE_VERIFIED** | Automated tests exercise the declared behavior. |
| **LEVEL 2 — NUMERICALLY_VERIFIED** | Known values are recovered within a stated numerical scope and tolerance. |
| **LEVEL 3 — CROSS_VALIDATED** | An external software or reference route is compared under a frozen protocol. |
| **LEVEL 4 — PHYSICALLY_VALIDATED** | A physical reference or calibrated experiment supports the scoped capability. |
| **LEVEL 5 — REPRODUCIBILITY_VALIDATED** | An independent party reproduced the declared result. |

### 13.1 Status table

| Capability | Evidence | Status | Limitations |
|-----------|----------|--------|-------------|
| Sa/Sq/Sz, frozen synthetic matrices | 48 cases, 144/144 within `1e-6 nm + 1e-6 relative` vs Gwyddion 2.71 | **LEVEL 3** | shared matrices, no preprocessing, three metrics only |
| Sa/Sq/Sz, public experimental GWY | 12 records, 36/36 shared‑matrix comparisons | **LEVEL 3** for algorithm track | parser track separately retained ten equivalences and two channel-count differences |
| Nanoscope III `.spm` | six files, 18/18 Sa/Sq/Sz and zero reported pixel delta | **LEVEL 2** | partial variants; `ACCIDENTAL_PRE_FREEZE_UNBLINDING`; no blind holdout |
| NanoSurf `.nid` mapping/orientation | synthetic byte/orientation tests and selected context comparisons | **LEVEL 1** | private corpus not distributed; no universal format coverage |
| Hertz/cone/DMT and force maps | analytical construction and synthetic recovery | **LEVEL 2** within synthetic scope | no certified tip/cantilever calibration or broad experimental campaign |
| Experimental JKR, WLC/FJC, SLS | analytical construction and synthetic recovery | **LEVEL 2** within synthetic scope | no physical-reference campaign; JKR and SLS remain explicitly experimental |
| KPFM, PSD/fractal, grains, resonance | unit and controlled software tests | **LEVEL 1** | no frozen public physical-reference campaign |
| Fathom workspace | offscreen GUI and architecture tests | **LEVEL 1** | platform and Qt behavior vary; GUI evidence does not upgrade numerical maturity |

### 13.2 Gwyddion as reference

Gwyddion is an external software route only where a campaign declares its version,
matrix handoff, wrapper, preprocessing, and tolerance. It is not universal ground truth.
The retained summaries live in
<https://github.com/kegouro/spmkit-validation/tree/main/evidence/campaigns>.
Passing those campaigns does not constitute physical validation or feature parity.

### 13.3 Simulator

The cantilever simulator is **educational only**. It models a damped harmonic
oscillator with additive white noise. It does not account for higher flexural modes,
fluid‑structure interaction, optical‑lever sensitivity, or real cantilever geometry.
Use it to understand qualitative behaviour, not for calibration or metrology.

---

## 14. Safety and interpretation warnings

- **Results require domain judgment.** A high R&sup2; does not guarantee that the
  chosen contact model is physically correct for your sample.
- **Calibration values matter.** Young's modulus extracted from force curves depends
  on tip radius (often uncertain), spring constant (calibration uncertainty), and
  contact model (an approximation). Report all three.
- **Units and conventions must be checked.** `SPMChannel.unit` tells you the physical
  unit. Do not assume all channels are in metres.
- **Experimental readers may misinterpret metadata.** Format‑specific metadata parsing
  is a best‑effort process, especially for formats reverse‑engineered with limited
  documentation.
- **Fitted parameters are not automatically physical truth.** A Hertz fit always
  produces a number. Whether that number represents the true Young's modulus depends
  on whether the sample is elastic, isotropic, homogeneous, and whether the contact
  is purely elastic within the fit range.
- **SPM‑Kit is not a medical, clinical, regulatory, or safety‑critical instrument.**
  Do not use it for diagnostic, treatment, or compliance decisions.
- **Preserve original data.** SPM‑Kit reads files without modifying them. Export
  results alongside the original instrument files.

---

## 15. Extensibility

### 15.1 Adding a file format

Register a `Reader` Protocol in `spmkit.plugins.v1` entry‑point group or in
`core/plugins/registry.py`. The reader must implement `inspect(path) → DatasetInfo`
and `load(path, kind) → SPMData | ForceVolume`.

```toml
[project.entry-points."spmkit.plugins.v1"]
my_format = "my_package.reader:MY_READER"
```

### 15.2 Adding a Fathom perspective

Define a `ModuleSpec` with `PanelSpec` and `PerspectiveSpec` entries, then register
it via the `spmkit.gui.modules` entry‑point group.

```python
from spmkit.gui.extensions import ModuleSpec, PanelSpec, PerspectiveSpec, ModuleContext

MY_MODULE = ModuleSpec(
    name="my_domain",
    panels=(PanelSpec("my_canvas", "My Canvas", _factory, area="central"),),
    perspectives=(PerspectiveSpec("my_view", "My View", ("navigator", "my_canvas")),),
)
```

```toml
[project.entry-points."spmkit.gui.modules"]
my_domain = "my_package.module:MY_MODULE"
```

### 15.3 Adding an analysis

Implement the `Analysis` Protocol and register via `spmkit.plugins.v1`.

### 15.4 Entry‑point groups

| Group | Purpose |
|-------|---------|
| `spmkit.plugins.v1` | Readers, analyses, domains |
| `spmkit.gui.modules` | Fathom modules (perspectives + panels) |

See `extending.md` for full details.

---

## 16. Troubleshooting

### Missing GUI extra
```
ImportError: cannot import name 'run' from 'spmkit.gui.app'
```
**Fix:** `pip install "spmkit[gui]"`

### Qt platform plugin error
```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb"
```
**Fix:** Install Qt platform dependencies (`libxcb-cursor0` on Debian/Ubuntu) or
set `QT_QPA_PLATFORM=offscreen` for headless environments.

### Unsupported file format
```
ValueError: unsupported extension: .xxx
```
**Fix:** Check that the file extension matches a supported format (`.nid`, `.nhf`,
`.gwy`, `.jpk-force`). For experimental readers, install `afm` or `jpk` extras.

### Missing optional dependency
```
ModuleNotFoundError: No module named 'scipy'
```
**Fix:** Reinstall SPMKit so its required dependencies are restored (for a development checkout: `python -m pip install -e .`).

### Empty or unexpected channels
```
data.names → ['Z-Axis', 'Phase'] but expected CPD
```
**Fix:** Verify with `spmkit info file.nid` that the channel exists. Not all scans
include all channel types.

### Large force‑volume memory use
**Fix:** Use lazy loading (`ForceVolume` does not hold all curves in RAM). For vectorised
processing, use the `--fast` path with CPU backend. Reduce grid resolution if possible.

### GPU / CuPy fallback
```
spmkit forcemap --backend gpu → falls back to cpu
```
**Fix:** CuPy is not bundled. Install it separately if GPU acceleration is desired:
`pip install cupy-cuda12x` (match your CUDA version).

### Export failure
```
PermissionError writing to ./results/
```
**Fix:** Check write permissions. Use `--output` to specify a writable directory.

### GUI crash logs
Fathom logs errors to the **Log** panel (visible in Batch perspective). For terminal
output, launch from a terminal: `spmkit gui 2>&1 | tee fathom.log`.

### macOS launch behaviour
macOS may require the application bundle or `python` to have accessibility
permissions if using screen recording or automation features. Qt 6 on macOS
typically works without special configuration.

---

## 17. Development and quality

### 17.1 Development setup

```bash
git clone https://github.com/kegouro/spmkit
cd spmkit
pip install -e ".[all,dev,test-gui]"
pre-commit install
```

### 17.2 Quality checks

```bash
make check        # lint + types + tests (the CI gate)
make lint         # ruff check
make format       # black + ruff --fix
make type         # mypy (strict on core)
make test         # pytest with coverage
```

### 17.3 GUI tests

```bash
QT_QPA_PLATFORM=offscreen pytest tests/gui -q
```

### 17.4 Documentation

```bash
pip install -e ".[docs]"
python -m mkdocs build --strict
```

### 17.5 CI

GitHub Actions workflow `.github/workflows/ci.yml` runs `make check` on push.
GUI tests are skipped in CI (no display), but unit and architecture tests always run.

---

## 18. SPM-Kit ecosystem relationship

The ecosystem has five identities with distinct responsibilities:

- **SPM‑Kit Core** reads demonstrated data variants and performs numerical analysis.
- **Fathom** invokes Core through an interactive scientific workspace.
- **SPM‑Kit Data Hunter** records public candidate datasets and provenance. Discovery is
  not validation, and not every located candidate is usable, redistributable, or suitable.
- **SPM‑Kit Phantoms** generates deterministic truth-bearing synthetic fixtures and
  declared corruptions without importing the analyzer under test.
- **SPM‑Kit Validation** runs frozen black-box campaigns against installed public SPM‑Kit
  interfaces and preserves evidence.

Artifacts move between repositories through declared files, manifests, hashes, and commands;
there is no automatic pipeline from every Data Hunter record into Validation. See the
[ecosystem portal](ecosystem/index.md) and [artifact contracts](ecosystem/contracts.md).

---

## 19. Citation, license, and contributions

### 19.1 How to cite

```bibtex
@software{spmkit2026,
  author = {José Labarca Baeza},
  title = {spmkit: Open-source AFM/KPFM analyser for scanning probe microscopy},
  year = {2026},
  version = {0.1.4},
  doi = {10.5281/zenodo.21303280},
  url = {https://github.com/kegouro/spmkit},
}
```

### 19.2 License

MIT. See `LICENSE` in the repository root.

### 19.3 Contributing

See [`CONTRIBUTING.md`](https://github.com/kegouro/spmkit/blob/main/CONTRIBUTING.md). Issues and pull requests are welcome at
<https://github.com/kegouro/spmkit/issues>.

### 19.4 Funding

This open‑source project has been developed without dedicated institutional funding.

### 19.5 Project status

**Alpha (source `0.1.5.dev0`; GitHub release `0.1.4`; PyPI `0.1.2`).** APIs may change
before 1.0. Evidence and compatibility remain capability- and format-specific.

---

## 20. Acknowledgements

José Labarca Baeza is the creator, author, and lead developer of SPM-Kit.

### English

Tomás Corrales and the SPM Lab at Universidad Técnica Federico Santa María provided selected experimental datasets and laboratory context during the development and evaluation of SPM-Kit.

María Saavedra Fredes and Benjamin Schleyer helped locate and share candidate datasets for the validation campaigns.

### Español

Tomás Corrales y el SPM Lab de la Universidad Técnica Federico Santa María proporcionaron datasets experimentales seleccionados y contexto de laboratorio durante el desarrollo y la evaluación de SPM-Kit.

María Saavedra Fredes y Benjamin Schleyer ayudaron a localizar y compartir datasets candidatos para las campañas de validación.

These acknowledgements do not imply that every located dataset was used, accepted,
redistributable, or scientifically suitable. They do not constitute software authorship,
institutional ownership, or endorsement.

---

## Appendices

### A. Quick reference

```bash
# Install the current source documented here
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"

# Inspect
spmkit info scan.nid

# Analyse
spmkit roughness scan.nid -c Z-Axis --level plane
spmkit psd scan.nid -c Z-Axis
spmkit analyze scan.nid -o ./results --tip-wf 4.8

# Figures
spmkit figure scan.nid -o topo.png --colormap batlow

# Convert
spmkit convert scan.nid scan.gwy

# Verify
spmkit verify scan.nid

# Force
spmkit forcecurve curve.jpk-force --model dmt --tip-radius 2e-8
spmkit forcemap volume.nid --fast -f maps.png
spmkit forcereport volume.nid -o report
spmkit forceexport volume.nid -o ./export
spmkit fbatch ./curves/ -o batch.csv

# Evaporation
spmkit evaporation ./tuning/ -k 0.3 -o evap.csv

# Grains
spmkit grains scan.nid --min-size 10

# GUI
spmkit gui [file]
spmkit gui --legacy
```

### B. Extras matrix

| Extra | Contents |
|-------|---------|
| (none) | Core CLI/Python API and dependency-free built-in paths; some formats need extras |
| `gui` | Fathom desktop workspace |
| `viz` | Publication figures, Crameri colormaps |
| `gwy` | Gwyddion `.gwy` read/write |
| `hdf5` | HDF5 import/export |
| `grains` | Grain detection |
| `report` | HTML/PDF reports |
| `nanosurf` | Optional NSFopen dependency |
| `afm` | Long‑tail format readers (afmformats) |
| `jpk` | JPK TIFF force curves |
| `parallel` | Multi‑core force‑volume processing |
| `pandas` | DataFrame export |
| `all` | Reader, GUI, visualization, report, grain, HDF5, and GWY extras declared by the package |
| `dev` | Developer tools |
| `test-gui` | GUI test runner |
| `docs` | Documentation builder |

### C. CLI command index

| Command | Category | Input |
|---------|----------|-------|
| `info` | Inspection | `.nid`, `.nhf` |
| `roughness` | Image analysis | `.nid`, `.nhf`, `.gwy` |
| `profile` | Profile extraction | `.nid`, `.nhf`, `.gwy` |
| `psd` | Spectral | `.nid`, `.nhf`, `.gwy` |
| `analyze` | Pipeline | `.nid`, `.nhf`, `.gwy` |
| `nanomech` | Force | `.nid` (spectroscopy) |
| `grains` | Image | `.nid`, `.nhf`, `.gwy` |
| `batch` | Batch | Folder of SPM files |
| `evaporation` | Resonance | Folder of `.nid` tuning files |
| `figure` | Figure | `.nid`, `.nhf`, `.gwy` |
| `convert` | Format | `.nid` |
| `verify` | Audit | `.nid` |
| `gui` | GUI | — (optional file) |
| `workspace` | GUI | Force‑curve file |
| `forcecurve` | Force | `.jpk-force`, `.nid` |
| `forcemap` | Force | `.nid` (force‑volume) |
| `forcereport` | Force | `.nid` (force‑volume) |
| `forceexport` | Force | `.nid` (force‑volume) |
| `fbatch` | Batch force | Folder of force curves |
| `jkr` | Force (experimental) | Calibrated force curve |

### D. Perspective index

| Key | Label | Module | Type |
|-----|-------|--------|------|
| `image` | Imagen | image | Image |
| `grains` | Granos | image | Image |
| `spectral` | Espectral | image | Image |
| `resonance` | Sintonía térmica | image | Image |
| `evaporation` | Evaporación | image | Image |
| `force` | Curva de fuerza | force | Force |
| `smfs` | SMFS | force | Force |
| `map` | Mapa | force | Force |
| `batch` | Batch | force | Force |
| `figure` | Figura | figure | Figure |
| `view3d` | Vista 3D | view3d | Image |
| `simulator` | Simulador | simulator | Educational |

### E. Validation status vocabulary

| Term | Definition |
|------|------------|
| **Level 0** | Claim documented without retained executable evidence |
| **Level 1** | Automated software verification within declared scope |
| **Level 2** | Known-value numerical recovery within declared scope and tolerance |
| **Level 3** | Frozen external cross-validation under declared conditions |
| **Level 4** | Scoped physical-reference validation |
| **Level 5** | Independent reproduction of the declared result |

### F. Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Command palette |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save project |
| `Ctrl+M` | Calculate map |
| `Ctrl+Shift+R` | Generate report |
| `Ctrl+Shift+L` | Toggle theme |
| `Ctrl+Shift+A` | Appearance settings |
| `Ctrl+E` | Export results (JSON) |
| `Ctrl+Shift+C` | Copy results |
| `Ctrl+P` | Pin curve |
| `Ctrl+←` / `Ctrl+→` | Previous / next curve |
| `Ctrl+Home` / `Ctrl+End` | First / last curve |
| `Ctrl+1`…`Ctrl+5` | Tab switching (legacy app) |

### G. Common output files

| File | Source | Contents |
|------|--------|----------|
| `batch_summary.csv` | `spmkit batch` | Roughness summary per file |
| `*_roughness.csv/json` | `spmkit analyze` | Roughness parameters |
| `*_kpfm.csv/json` | `spmkit analyze` | KPFM/CPD statistics |
| `figure.png/svg/pdf` | `spmkit figure` | Publication figure |
| `scan.gwy` | `spmkit convert` | Gwyddion‑compatible file |
| `scan.h5` | `spmkit convert` | HDF5 archive |
| `force_batch.csv` | `spmkit fbatch` | Force curve summary |
| `maps.png` | `spmkit forcemap -f` | Property map visualisation |
| `informe.html/pdf` | `spmkit forcereport` | Full force‑volume report |
| `export/` | `spmkit forceexport` | Complete export bundle |
| `.spmproj` | Fathom `Ctrl+S` | Project file (YAML) |

---

*End of SPM‑Kit &middot; Fathom Usage Guide &mdash; source 0.1.5.dev0 · GitHub 0.1.4 · PyPI 0.1.2*
