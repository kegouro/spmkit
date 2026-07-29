---
title: SPM-Kit visual-system fixture
description: Internal regression fixture for the Pharos-aligned SPM-Kit design system.
hide:
  - navigation
  - toc
---

# SPM-Kit visual-system fixture

This page is intentionally absent from public navigation. It gives maintainers a
stable surface for visual, contrast, responsive and accessibility regression
checks without turning the documentation into a style-guide destination.

## Semantic color roles

<div class="spm-token-grid">
  <div class="spm-swatch" style="--swatch:var(--spm-canvas);--swatch-ink:var(--spm-ink)">canvas<br><code>--spm-canvas</code></div>
  <div class="spm-swatch" style="--swatch:var(--spm-surface);--swatch-ink:var(--spm-ink)">surface<br><code>--spm-surface</code></div>
  <div class="spm-swatch" style="--swatch:var(--spm-surface-raised);--swatch-ink:var(--spm-ink)">raised<br><code>--spm-surface-raised</code></div>
  <div class="spm-swatch" style="--swatch:var(--spm-action);--swatch-ink:var(--spm-action-ink)">action<br><code>--spm-action</code></div>
  <div class="spm-swatch" style="--swatch:var(--spm-beam);--swatch-ink:var(--spm-beam-ink)">SPM beam<br><code>--spm-beam</code></div>
  <div class="spm-swatch" style="--swatch:var(--spm-signal);--swatch-ink:var(--spm-canvas)">data signal<br><code>--spm-signal</code></div>
</div>

## Actions

<div class="spm-fixture-row">
  <a class="spm-button spm-button--primary" href="#actions">Primary action</a>
  <a class="spm-button spm-button--secondary" href="#actions">Secondary action</a>
  <a class="spm-button spm-button--quiet" href="#actions">Quiet action</a>
</div>

## Status vocabulary

<div class="spm-fixture-row">
  <span class="spm-status spm-status--pass">PASS</span>
  <span class="spm-status spm-status--fail">FAIL</span>
  <span class="spm-status spm-status--blocked">BLOCKED</span>
  <span class="spm-status spm-status--not-run">NOT_RUN</span>
  <span class="spm-status">ALPHA</span>
</div>

## Editorial and evidence panels

<div class="spm-capability-grid">
  <article class="spm-panel spm-panel--capability">
    <h3>Image metrology</h3>
    <p>Open editorial grouping with no decorative box. The rule carries hierarchy while the content remains primary.</p>
  </article>
  <article class="spm-panel spm-panel--capability">
    <h3>Force spectroscopy</h3>
    <p>Hertz, Sneddon, DMT and experimental JKR routes remain named with their scientific boundaries.</p>
  </article>
  <article class="spm-panel spm-panel--evidence">
    <h3>Evidence result</h3>
    <p><span class="spm-status spm-status--pass">PASS</span> A bordered panel is reserved for evidence that needs a durable boundary.</p>
  </article>
</div>

## Canonical evidence ladder

<div class="spm-evidence-ladder" tabindex="0" aria-label="Example SPM-Kit evidence ladder">
  <article class="spm-evidence-step"><span class="spm-step-label">01 · FIND</span><h3>Data Hunter</h3><p>Locates candidate evidence for human review.</p></article>
  <article class="spm-evidence-step"><span class="spm-step-label">02 · DEFINE</span><h3>Phantoms</h3><p>Creates declared numerical truth.</p></article>
  <article class="spm-evidence-step"><span class="spm-step-label">03 · TEST</span><h3>Validation</h3><p>Executes an external public-interface campaign.</p></article>
  <article class="spm-evidence-step"><span class="spm-step-label">04 · COMPUTE</span><h3>SPM-Kit Core</h3><p>Performs the analysis under evaluation.</p></article>
  <article class="spm-evidence-step"><span class="spm-step-label">05 · OPERATE</span><h3>Fathom</h3><p>Lets a researcher inspect the same Core result.</p></article>
</div>

## Scientific content

<div class="spm-io">
  <span><b>Input</b>calibrated force and indentation</span>
  <span aria-hidden="true">→</span>
  <span><b>Output</b>declared model parameters and fit evidence</span>
</div>

For a spherical or paraboloidal indenter, the Hertz route uses

$$
F = \frac{4}{3} E^* \sqrt{R}\,\delta^{3/2}.
$$

| Level | Meaning | Boundary |
|---|---|---|
| `LEVEL 1` | Software verified | Passing tests do not establish physical validity |
| `LEVEL 2` | Numerically verified | Synthetic recovery is not a calibrated specimen |
| `LEVEL 3` | Cross validated | Agreement is campaign- and tolerance-specific |

```python
from spmkit.core import mechanics

result = mechanics.fit_hertz(force, indentation, radius=tip_radius)
```

!!! warning "Limitations stay visible"

    Status color supports the text label; it never replaces the named state,
    evidence route or scientific limitation.
