# SPM-Kit ecosystem

SPM-Kit is the central product of a scientific infrastructure ecosystem. The
components work together but are designed to be useful independently.

## The chain

```mermaid
flowchart TB
    DH["Data Hunter<br>discover public datasets"] --> PH
    PH["Phantoms<br>synthetic ground truth"] --> SK
    SK["SPM-Kit<br>numerical analysis"] --> FT
    FT["Fathom<br>interactive workspace"] --> OUT["figures · maps · reports · provenance"]
    SK --> VAL["Validation<br>independent campaigns"]
    VAL --> OUT
```

> **Find the evidence → define the truth → test the system externally → preserve the result.**

## Components

<div class="fathom-cards" markdown>

<div class="fathom-card" markdown>
<p class="card-role">Core engine</p>
<h3><a href="spmkit.md">SPM-Kit</a></h3>
<p class="card-desc">Numerical engine, Python API, CLI. <code>pip install spmkit</code>.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Workspace</p>
<h3><a href="fathom.md">Fathom</a></h3>
<p class="card-desc">PyQt6 desktop workspace for visualization and analysis.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Synthetic truth</p>
<h3><a href="phantoms.md">Phantoms</a></h3>
<p class="card-desc">Deterministic synthetic surfaces with known ground truth.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Discovery</p>
<h3><a href="data-hunter.md">Data Hunter</a></h3>
<p class="card-desc">Discover and triage public AFM/SPM datasets.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Evidence</p>
<h3><a href="validation.md">Validation</a></h3>
<p class="card-desc">External black-box validation harness with frozen evidence.</p>
</div>

<div class="fathom-card" markdown>
<p class="card-role">Umbrella</p>
<h3><a href="pharos.md">Pharos</a></h3>
<p class="card-desc">A broader collection of open scientific tools.</p>
</div>

</div>
