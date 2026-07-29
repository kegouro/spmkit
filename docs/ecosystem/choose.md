---
title: Which component do I need?
description: An accessible decision guide for selecting SPM-Kit Core, Fathom, Data Hunter, Phantoms, or Validation.
---

# Which component do I need?

Start with the scientific task. Repositories are boundaries of responsibility,
not five interchangeable products.

<div class="spm-decision-tree">
  <details open><summary>I want to analyze data</summary><div><p><strong>Interactively:</strong> start with <a href="../fathom/">Fathom</a>. It operates SPM-Kit Core through visual perspectives.</p><p><strong>Programmatically, in notebooks, batch jobs, CI or HPC:</strong> start with <a href="../spmkit/">SPM-Kit Core</a>.</p></div></details>
  <details><summary>I want to test an algorithm</summary><div><p><strong>Against a known numerical surface:</strong> generate truth with <a href="../phantoms/">Phantoms</a>, then execute the comparison through <a href="../validation/">Validation</a>.</p><p><strong>Against external software or a published reference:</strong> start with Validation and freeze reference independence, parameters and tolerance before execution.</p></div></details>
  <details><summary>I need a native-format fixture</summary><div><p>Use <a href="../data-hunter/">Data Hunter</a> to find candidates, then manually review format, rights and content. A raw-only file can exercise a Core reader; it cannot validate an analysis result.</p></div></details>
  <details><summary>I want to contribute a dataset</summary><div><p>Begin with Data Hunter's evidence taxonomy and lawful provenance. If accepted, design the narrow fixture or Validation campaign separately. Do not upload restricted or personally sensitive data.</p></div></details>
  <details><summary>I want reproducible analysis over many files</summary><div><p>Use Core through Python or `spmkit batch`/`fbatch`. Preserve versions, command, channel, units, preprocessing and input hashes. Fathom remains useful for inspecting representative cases.</p></div></details>
  <details><summary>I want to add a reader</summary><div><p>Implement the versioned `spmkit.plugins.v1` reader contract in Core. Use a lawful native file as a parser fixture, add synthetic edge cases and define a later external validation path.</p></div></details>
  <details><summary>I want to add a scientific capability</summary><div><p>Implement a pure Core function first, create a known recovery case with Phantoms, define an external evidence route with Validation, expose CLI/API, and add a Fathom panel only after numerical behavior is stable.</p></div></details>
  <details><summary>I want to propose physical validation</summary><div><p>Start in Validation. Define the mensurand, calibrated reference, uncertainty, traceability, lawful data handling, blinded or independent design and pass/fail policy. Data Hunter may locate leads but cannot certify them.</p></div></details>
</div>

<div class="spm-decision-fallback">
  <strong>No JavaScript required.</strong> The branches above are native HTML
  disclosure controls. If they are unavailable, use the complete table below.
</div>

## Static decision table

| Need | Primary component | Companion | Allowed conclusion | Not allowed |
|---|---|---|---|---|
| inspect an image or curve visually | Fathom | Core | the configured Core result was inspected interactively | the view is physically validated |
| Python/CLI/HPC analysis | Core | Fathom for spot-checking | the public function/command produced the result | all formats/models are equally mature |
| known synthetic answer | Phantoms | Validation | a numerical truth and corruption sequence are known | physical validity |
| external reference comparison | Validation | Core/Phantoms | the frozen comparison met or failed its rule | universal equivalence |
| public-data discovery | Data Hunter | human review | a record may support a named role | dataset certification |
| format fixture | Data Hunter → Core | Validation later | reader behavior can be exercised | analysis correctness |
| dataset contribution | Data Hunter → Validation | Core | a reviewed case can enter design | automatic acceptance/redistribution |
| plugin development | Core | Phantoms/Validation/Fathom | a versioned contract can be implemented | stable 1.0 API promise |

## Still unsure?

Use [SPM-Kit Core](spmkit.md) if the task is a calculation. Use
[Fathom](fathom.md) if the task is operating that calculation visually. Use
the three companion repositories only when the task is evidence discovery,
known truth or external validation.

[Installation matrix](install.md) · [Workflow tutorials](workflows/index.md)
