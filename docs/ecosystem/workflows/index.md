---
title: Ecosystem workflows
description: Five executable AFM/SPM workflows connecting analysis, synthetic truth, data discovery, external validation, plugins, and Fathom.
---

# Ecosystem workflows

Each tutorial states what evidence it produces and what conclusion remains out
of reach. Replace example paths with files you are authorized to use.

## Workflow A: analyze an experimental file

**Components:** SPM-Kit Core + Fathom
**Prerequisite:** a supported file with known source, rights, channel semantics and calibration context.

```bash
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"
spmkit info scan.nid
spmkit analyze scan.nid --channel Z-Axis --level plane --output results/
spmkit gui scan.nid
```

1. Check `spmkit info` for channels, direction, units and field of view.
2. Run the declared channel/leveling path.
3. In Fathom, inspect routing and choose **Imagen** (`image`) or the compatible force perspective.
4. Confirm parameters and visible QC; do not repair an implausible result by hiding it.
5. Export the result/figure and save a `.spmproj` when applicable.
6. Preserve input hash, package version, command/project, parameters and outputs.

**Expected output:** roughness CSV/JSON and optional KPFM CSV/JSON; Fathom
project/figure/report depending on the selected route.
**Evidence produced:** a reproducible software execution record for this file and configuration.
**Allowed conclusion:** SPM-Kit produced the named result through the declared path.
**Not allowed:** the instrument calibration, model or entire format family is physically validated.

## Workflow B: test roughness recovery on known truth

**Components:** Phantoms + Validation + SPM-Kit Core
**Prerequisite:** editable installs of all three packages in one environment.

```bash
spmkit-phantoms --outdir cases --seed 42
python -m json.tool cases/inclined_noisy/corruption_manifest.json
spmkit analyze cases/inclined_noisy/observed.npz --level plane --output direct-results/

spmkit-validation campaign \
  spmkit-validation/campaigns/smoke_v0.1.yaml \
  validation-runs/ \
  --spmkit "$(command -v spmkit)"
```

1. Record the analytical surface and expected clean Sa/Sq/Sz.
2. Keep the clean and observed arrays separate.
3. Inspect seed, corruption order, masks and canonical hashes.
4. Freeze a campaign with metric definitions and tolerance before promotion.
5. Execute the installed public CLI and capture results.
6. Compare expected and observed quantities; retain every row.

**Expected output:** NPZ bundles/manifests, SPM-Kit CSV/JSON, Validation
`cases.csv` and captured streams.
**Evidence produced:** numerical recovery/difference data for controlled cases.
**Allowed conclusion:** a frozen campaign may support a narrow `LEVEL 2` claim.
**Not allowed:** synthetic recovery is physical validation; the current smoke
definition itself has no promoted tolerance and stays `TODO-SCIENTIFIC-DECISION`.

## Workflow C: find a public format fixture

**Components:** Data Hunter + human review + SPM-Kit Core
**Prerequisite:** network/API use is authorized and an explicit campaign budget is chosen.

```bash
spmkit-data-hunter campaign create reader-fixtures \
  --preset topography force \
  --source zenodo figshare \
  --max-runtime 2h \
  --max-records 0 \
  --output hunt
spmkit-data-hunter campaign run reader-fixtures --output hunt
spmkit-data-hunter download plan reader-fixtures --output hunt \
  --level gold silver bronze --category raw
```

1. Review candidate relevance, native format, license and redistribution rights.
2. Verify checksums and inspect metadata without executing downloaded content.
3. Download only the accepted record with bounded size settings.
4. Run `spmkit info candidate.ext` in a quarantined/appropriate environment.
5. Add the smallest lawful fixture and parser assertions.
6. Document that it is a reader fixture unless a matched scientific reference exists.

**Expected output:** campaign databases/export views, selected raw file and reader inspection record.
**Evidence produced:** parser/metadata fixture provenance.
**Allowed conclusion:** the reader handles the demonstrated fixture/variant.
**Not allowed:** the file validates image/force analysis or may be redistributed without review.

## Workflow D: build an independent cross-comparison

**Components:** reviewed external data or Data Hunter + Validation + Core + declared external reference.

1. Define one mensurand and exact operation order.
2. Establish the reference implementation/data lineage and independence class.
3. Freeze input hashes, units, preprocessing, software versions and tolerance before observing results.
4. Execute SPM-Kit through a public interface in an isolated environment.
5. Execute the reference route without importing SPM-Kit output into its expected calculation.
6. Compare per case/metric and preserve passes, failures, errors and missing artifacts.
7. Publish the narrow claim, result rows, protocol, lock and limitations together.

```text
input hash + SUT identity + reference identity + operation + tolerance
                              ↓
                    immutable campaign lock
                              ↓
                both outputs + comparison rows
                              ↓
                   scoped evidence statement
```

**Expected output:** frozen design/lock, captured outputs, result rows, summary and audit.
**Evidence produced:** candidate `LEVEL 3` evidence when independence and tolerance are defensible.
**Allowed conclusion:** only the named metrics/cases/version met or failed the frozen rule.
**Not allowed:** universal equivalence, physical validity or feature-wide validation.

## Workflow E: add an ecosystem capability

**Components:** Core plugin/API + Phantoms + Validation + Fathom where appropriate.

1. Define the scientific requirement, units, failure modes and allowed claim.
2. Implement a pure Core capability or `spmkit.plugins.v1` reader.
3. Add a deterministic analytical or synthetic recovery case.
4. Expose the stable route through the public Python API and CLI.
5. Define an external validation path and reference-independence argument.
6. Add a Fathom panel/perspective only after numerical behavior and result objects are stable.
7. Document inputs, outputs, evidence level and known limitation.

**Expected output:** Core implementation, public contract, recovery case,
campaign proposal/evidence and optional Fathom surface.
**Evidence produced:** capability-specific software and numerical records.
**Allowed conclusion:** maturity advances only as each retained evidence level is met.
**Not allowed:** a GUI panel or passing unit test makes the capability physically validated.

## Preservation checklist

- exact repository commits and package versions;
- Python/OS and relevant optional dependency versions;
- lawful input source, license and hashes;
- command vectors or project/recipe;
- units, field of view, calibration and preprocessing;
- model parameters and frozen tolerance;
- outputs, failures, warnings and incident records;
- allowed and disallowed scientific conclusion.

[Artifact contracts](../contracts.md) ·
[Campaign browser](../validation.md) ·
[Return to ecosystem overview](../index.md)
