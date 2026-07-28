---
title: SPM-Kit · Fathom
---

<div class="fathom-hero" markdown>

<img src="images/brand/fathom_banner_new.jpeg" alt="SPM-Kit · Fathom" width="100%">

# SPM-Kit · Fathom

<p class="tagline">Fathom is the scientific workspace. SPM-Kit is the open numerical engine beneath it.</p>

<span class="status-badge">Alpha · 0.1.5.dev0</span>

<div class="fathom-cta" markdown>
<a class="primary" href="getting-started.md">Get started</a>
<a class="secondary" href="manual/index.md">Manual</a>
<a class="secondary" href="theory/index.md">Theory</a>
<a class="secondary" href="ecosystem/validation.md">Validation</a>
<a class="secondary" href="https://github.com/kegouro/spmkit">GitHub</a>
</div>

</div>

---

## The problem

AFM/SPM data analysis is fragmented across proprietary tools, opaque processing
pipelines, and format-specific software that makes it hard to inspect what
transformations were applied to your data. Researchers need to separate
**computation**, **interface**, and **evidence** — and to trace every result
back to its source.

SPM-Kit solves this by providing an open numerical engine with a transparent
pipeline: every step is inspectable, every format reader is traceable, and every
physical model is validated against known ground truth.

---

## What it can do

| Domain | Capabilities |
|---|---|
| **Imaging & surface metrology** | ISO 25178 roughness (Sa, Sq, Sz, Ssk, Sku), leveling, profiles, PSD, Hurst exponent |
| **Force spectroscopy & nanomechanics** | Hertz, DMT, JKR, WLC, FJC, SLS relaxation, force-volume maps |
| **Single-molecule force spectroscopy** | Event detection, contour extraction, baseline correction, multi-peak analysis |
| **Resonance & mass sensing** | Thermal tune (SHO fit), Q factor, resonance frequency, mass sensing (d² law) |
| **Reproducible workflows & reporting** | Recipe (YAML pipeline), HTML/PDF reports, provenance, byte-level traceability |

---

## Architecture

```mermaid
flowchart TB
    Files["Instrument files<br>.nid · .nhf · .gwy · .spm"] --> Core
    subgraph Core["SPM-Kit core (src/spmkit/core/)"]
        Readers["Readers"]
        Analysis["Analysis"]
        Export["Export & verification"]
    end
    Core --> API["Python API"]
    Core --> CLI["CLI (spmkit)"]
    Core --> Fathom["Fathom (PyQt6 workspace)"]
    API --> Output["figures · maps · reports · provenance"]
    CLI --> Output
    Fathom --> Output
```

All numerical analysis lives in `core/`. The CLI and Fathom only orchestrate it — they never implement analysis or touch parsers directly.

---

## Scientific evidence

| Capability | Evidence | Level |
|---|---|---|
| Physical models (Hertz, WLC, FJC, JKR, SLS, SHO) | Synthetic recovery tests — parameters recovered within tolerance | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| Sa, Sq, Sz (synthetic surfaces) | 18/18 cross-comparisons vs Gwyddion 2.71 | <span class="level-badge level-3">LEVEL 3 CROSS_VALIDATED</span> |
| Nanoscope III `.spm` reader | 18/18 within tolerance, 6 experimental files | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| `.nid` format round-trip | Machine-precision correlation vs Gwyddion | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |
| JPK TIFF, `.ibw`, NT-MDT | Readers implemented, not cross-validated | <span class="level-badge level-exp">experimental</span> |

**Verification coverage:** 741 unique automated tests, plus 18 external cross-comparisons of Sa, Sq and Sz against Gwyddion 2.71.

---

## Ecosystem

<div class="fathom-cards" markdown>

<div class="fathom-card" markdown>
<p class="card-role">Core engine</p>
<h3><a href="ecosystem/spmkit.md">SPM-Kit</a></h3>
<p class="card-desc">Numerical engine, Python API, CLI. The package you install with <code>pip install spmkit</code>.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Workspace</p>
<h3><a href="ecosystem/fathom.md">Fathom</a></h3>
<p class="card-desc">Interactive PyQt6 desktop workspace for visualization, analysis, and reporting.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Synthetic truth</p>
<h3><a href="ecosystem/phantoms.md">Phantoms</a></h3>
<p class="card-desc">Deterministic synthetic surfaces with known ground truth, controlled corruptions, canonical hashes.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Discovery</p>
<h3><a href="ecosystem/data-hunter.md">Data Hunter</a></h3>
<p class="card-desc">Discover, catalog, and triage public AFM/SPM datasets for validation campaigns.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Evidence</p>
<h3><a href="ecosystem/validation.md">Validation</a></h3>
<p class="card-desc">External black-box validation harness. Runs SPM-Kit via subprocess, preserves reproducible evidence.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Umbrella</p>
<h3><a href="ecosystem/pharos.md">Pharos</a></h3>
<p class="card-desc">A broader collection of open scientific tools built around reproducibility and transparent computation.</p>
</div>

</div>

> **Find the evidence → define the truth → test the system externally → preserve the result.**

---

## Learn & explore

<div class="fathom-cards" markdown>

<div class="fathom-card" markdown>
<h3><a href="theory/index.md">Theory guide</a></h3>
<p class="card-desc">AFM principles, operating modes, force spectroscopy, KPFM, roughness, resonance — connected to SPM-Kit implementations.</p>
</div>

<div class="fathom-card" markdown>
<h3><a href="manual/index.md">User manual</a></h3>
<p class="card-desc">Full GUI guide, CLI reference, PDF reader, keyboard shortcuts, and workflows.</p>
</div>

<div class="fathom-card" markdown>
<h3><a href="getting-started.md">Getting started</a></h3>
<p class="card-desc">Install, open your first file, run your first analysis in 5 minutes.</p>
</div>

<div class="fathom-card" markdown>
<h3><a href="api.md">Python API</a></h3>
<p class="card-desc">Direct access to readers, models, analysis functions, and export utilities.</p>
</div>

<div class="fathom-card" markdown>
<h3><a href="ecosystem/validation.md">Validation evidence</a></h3>
<p class="card-desc">Campaign records, tolerance budgets, receipts, and cross-validation results.</p>
</div>

<div class="fathom-card" markdown>
<h3><a href="extending.md">Extending</a></h3>
<p class="card-desc">Add file formats, analysis methods, and Fathom perspectives through the plugin system.</p>
</div>

</div>

---

## What SPM-Kit does not claim

!!! warning "Honest scope"

    - **Alpha software.** APIs may change before 1.0.
    - **No certified metrological traceability.** Results are not certified reference values.
    - **Cross-validation is limited.** Sa, Sq, Sz validated on 6 synthetic surfaces against Gwyddion 2.71 — not on all formats, all metrics, or all instruments.
    - **No blind holdout.** The Nanoscope campaign had `ACCIDENTAL_PRE_FREEZE_UNBLINDING`.
    - **No physical validation (LEVEL 4) or interlaboratory reproducibility (LEVEL 5).**
    - **Experimental formats** (JPK TIFF, `.ibw`, NT-MDT) are implemented but not cross-validated.
    - **Not a Gwyddion replacement.** The reference uses Gwyddion libraries through a frozen wrapper; this is not universal equivalence.

---

## Citation

If you use SPM-Kit or Fathom in a publication, cite it per [`CITATION.cff`](https://github.com/kegouro/spmkit/blob/main/CITATION.cff).

<div align="center">

[![DOI](https://zenodo.org/badge/1270254374.svg)](https://zenodo.org/badge/latestdoi/1270254374)

<sub>Independently designed and developed by José Labarca Baeza · SPM Lab, UTFSM · MIT License © 2026</sub>

</div>
