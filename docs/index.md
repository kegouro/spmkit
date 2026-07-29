---
title: SPM-Kit · Open AFM/SPM analysis
description: Open numerical analysis and an interactive Fathom workspace for AFM, KPFM, force spectroscopy, surface metrology, and reproducible scientific evidence.
hide:
  - toc
---

<section class="portal-hero">
  <p class="portal-kicker">Open AFM/SPM computation · Alpha</p>
  <h1>Inspect the computation, not just the picture.</h1>
  <p class="portal-lede">SPM-Kit is the open numerical engine for AFM, KPFM and force-spectroscopy data. Fathom is the interactive scientific workspace over that same core. Together they keep the route from instrument file to reported result visible.</p>
  <div class="portal-signal">
    <span><strong>CORE</strong> Python + CLI</span>
    <span><strong>WORKSPACE</strong> Fathom</span>
    <span><strong>STATUS</strong> 0.1.5.dev0 · alpha</span>
    <span><strong>AUTHOR</strong> José Labarca Baeza</span>
  </div>
  <div class="portal-actions">
    <a href="getting-started/installation/">Get started</a>
    <a href="manual/">Open manual</a>
    <a href="theory/">Study the theory</a>
    <a href="SCIENTIFIC_STATUS/">Inspect evidence</a>
    <a href="https://github.com/kegouro/spmkit">GitHub</a>
  </div>
</section>

<div class="io-strip">
  <span><b>Numerical engine</b> SPM-Kit computes</span>
  <span aria-hidden="true">→</span>
  <span><b>Scientific workspace</b> Fathom lets the researcher inspect, configure and operate those computations interactively</span>
</div>

## Why this exists

AFM/SPM analysis often crosses proprietary formats, hidden preprocessing, manual
exports and software-specific defaults. A plausible image is easy to produce;
an inspectable chain of calibrated data, declared operations and preserved
evidence is harder.

SPM-Kit separates that chain into explicit responsibilities:

- readers inspect instrument files and construct calibrated domain models;
- pure Core functions perform numerical analysis without GUI state;
- the Python API and CLI support notebooks, batch jobs, servers and CI;
- Fathom operates the same functions through task-oriented perspectives;
- exports preserve results and available provenance;
- independent companion repositories discover evidence, define synthetic truth
  and execute external validation campaigns.

The project is independently created, authored and led by **José Labarca
Baeza**. It is alpha software: useful, testable and open to inspection, but not
a certified metrology system.

## What it computes

<div class="intent-grid">
  <article class="intent-card">
    <h3>Image metrology</h3>
    <p>Plane, polynomial and row leveling; Sa, Sq, Sz, Ssk and Sku; profiles, grain statistics, radial PSD, Hurst exponent and correlation length.</p>
  </article>
  <article class="intent-card">
    <h3>Force spectroscopy</h3>
    <p>Baseline and contact detection, Hertz, Sneddon, DMT and experimental JKR fitting, adhesion, dissipation, force-volume property maps and reports.</p>
  </article>
  <article class="intent-card">
    <h3>KPFM</h3>
    <p>Contact-potential statistics and sample work-function calculation when a calibrated tip work function is supplied.</p>
  </article>
  <article class="intent-card">
    <h3>SMFS</h3>
    <p>Retract-curve baseline correction, event detection, WLC/FJC chain fitting and per-event result inspection.</p>
  </article>
  <article class="intent-card">
    <h3>Resonance</h3>
    <p>Thermal spectrum extraction, SHO fitting, effective mass, frequency-shift mass sensing and declared evaporation models.</p>
  </article>
  <article class="intent-card">
    <h3>Reporting and provenance</h3>
    <p>CSV, JSON, figures, HTML/PDF reports, recipes, project files, hashes and traceability records where the workflow exposes them.</p>
  </article>
</div>

## One numerical core, two operating surfaces

```text
instrument file
      ↓
reader inspection → calibrated SPMData / ForceCurve / ForceVolume
      ↓
SPM-Kit Core → typed numerical result
      ↓
Python API ───────── CLI ───────── Fathom
      ↓              ↓              ↓
notebook/batch    artifacts      interactive inspection
      └──────────────┴──────────────┘
          exports · reports · provenance
```

The boundary is deliberate. `src/spmkit/core/` contains the parsers, domain
models and analysis. `src/spmkit/cli/` and `src/spmkit/gui/` orchestrate public
Core APIs. Fathom is not a second numerical implementation.

[Read the architecture reference](ARCHITECTURE.md) ·
[Use the Python API](api.md) ·
[Inspect the CLI](cli.md)

## Scientific evidence, in scope

The strongest retained public evidence is narrow and named. Numbers below are
campaign results, not universal software scores.

| Capability | Retained result | Evidence | Boundary |
|---|---:|---|---|
| Sa, Sq and Sz on 48 frozen synthetic matrices | **144/144** comparisons within the frozen threshold against Gwyddion 2.71 | `LEVEL 3 — CROSS_VALIDATED` | Shared matrices; no physical acquisition or universal equivalence |
| Sa, Sq and Sz on 12 public experimental GWY records | **36/36** shared-matrix comparisons within threshold | `LEVEL 3` for the shared-matrix metric route | Public data are not physical ground truth; parser tracks were observational |
| Limited Nanoscope III parser scope | **18/18** roughness comparisons within threshold; zero reported pixel delta on six demonstrated files | `LEVEL 2 — NUMERICALLY_VERIFIED` | Accidental pre-freeze unblinding; no blind holdout or family-wide claim |
| Physical models and numerical paths | deterministic synthetic recovery and software tests | capability-specific `LEVEL 1` or `LEVEL 2` | Synthetic recovery is not physical validation |

No retained campaign establishes general physical validation (`LEVEL 4`) or
interlaboratory reproducibility (`LEVEL 5`). [Read the scientific status](SCIENTIFIC_STATUS.md)
and [campaign evidence](VALIDATION.md).

## The ecosystem

<div class="workflow-rail" aria-label="SPM-Kit ecosystem evidence chain">
  <article class="workflow-stage"><span class="step">01 · FIND</span><h3>Data Hunter</h3><p>Discovers and classifies candidate public evidence.</p></article>
  <article class="workflow-stage"><span class="step">02 · DEFINE</span><h3>Phantoms</h3><p>Creates controlled arrays with declared numerical truth.</p></article>
  <article class="workflow-stage"><span class="step">03 · TEST</span><h3>Validation</h3><p>Invokes the installed package through public interfaces.</p></article>
  <article class="workflow-stage"><span class="step">04 · COMPUTE</span><h3>SPM-Kit Core</h3><p>Performs the analysis under evaluation.</p></article>
  <article class="workflow-stage"><span class="step">05 · OPERATE</span><h3>Fathom</h3><p>Lets researchers inspect and operate the same Core interactively.</p></article>
</div>

**Find the evidence → define the truth → test the system externally → preserve
the result.** The order is explanatory, not an automatic data pipeline. Human
review separates discovery from validation, Phantoms stays independent from the
analyzer, and Validation records reference independence campaign by campaign.

<div class="portal-actions">
  <a href="ecosystem/">Explore the ecosystem</a>
  <a href="ecosystem/choose/">Choose a component</a>
  <a href="ecosystem/workflows/">Run a workflow</a>
  <a href="ecosystem/validation/">Inspect campaign evidence</a>
</div>

## Start with the task, not the repository

| I need to… | Start here |
|---|---|
| Inspect and analyze a file interactively | [Fathom quick start](getting-started/fathom-quick-start.md) |
| Run reproducible Python or cluster analysis | [SPM-Kit Core](ecosystem/spmkit.md) |
| Learn the physics behind the computation | [Theory portal](theory/index.md) |
| Reproduce a documented analysis | [Workflow tutorials](ecosystem/workflows/index.md) |
| Evaluate a metric against known truth | [Phantoms](ecosystem/phantoms.md) then [Validation](ecosystem/validation.md) |
| Find a public native-format fixture | [Data Hunter](ecosystem/data-hunter.md) |
| Audit the evidence behind a claim | [Scientific evidence](SCIENTIFIC_STATUS.md) |
| Add a reader or scientific capability | [Extending SPM-Kit](extending.md) |

## Install without ambiguity

The current source tree is `0.1.5.dev0`. The latest GitHub release is `0.1.4`,
while PyPI currently serves `0.1.2`; therefore `pip install spmkit` does **not**
install the latest GitHub release. Use the development install below when you
need the documented portal surface:

```bash
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"
spmkit --version
spmkit gui
```

See the [installation guide](getting-started/installation.md) for reproducible
Git tags, editable development installs, extras and platform notes. Companion
repositories have separate packages and are not installed by `spmkit`.

## Honest scope

!!! warning "What this site does not claim"

    - SPM-Kit is alpha software and APIs may change before 1.0.
    - It is not a certified instrument-control or metrological-traceability system.
    - A supported parser is not automatically validated for every instrument variant.
    - Synthetic recovery does not replace calibrated physical reference materials.
    - A public dataset is a lead, not automatically a reference.
    - Black-box execution separates processes; reference independence still requires an explicit argument.
    - Not every feature has the same evidence level. Read the status beside the capability you use.

## Citation and acknowledgement

SPM-Kit and Fathom were created and are led by **José Labarca Baeza**. Cite the
software using [`CITATION.cff`](https://github.com/kegouro/spmkit/blob/main/CITATION.cff)
and the guidance on the [citation page](CITATION.md).

Tomás Corrales and the SPM Lab at Universidad Técnica Federico Santa María
provided selected experimental datasets and laboratory context during the
development and evaluation of SPM-Kit.

María Saavedra Fredes and Benjamin Schleyer helped locate and share candidate
datasets for the validation campaigns.

These contributions are acknowledgements, not software authorship,
institutional ownership or an assertion that every located dataset was used,
accepted, redistributable or scientifically suitable.
