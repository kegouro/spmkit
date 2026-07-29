---
title: SPM-Kit Validation
description: External black-box campaigns, frozen contracts, retained evidence, exact tolerances, failures, blockers, and reproduction guidance.
---

<section class="component-section" data-component="validation">
  <picture><source type="image/webp" srcset="../../assets/ecosystem/validation/banner-640.webp 640w, ../../assets/ecosystem/validation/banner-1280.webp 1280w" sizes="(max-width: 1280px) 100vw, 1280px"><img class="brand-banner" src="../../assets/ecosystem/validation/banner.png" width="1983" height="793" alt="SPM-Kit Validation external black-box evidence banner" loading="eager" fetchpriority="high"></picture>
  <div class="component-copy">
    <div><p class="component-role">SPM-Kit Validation · External evidence</p><h1>Test what the installed package actually does</h1><p>Validation freezes campaign inputs, executable identity, reference route and tolerances, invokes public interfaces in a separate process and preserves the result with its limitations.</p></div>
    <div><span class="status-ribbon">Alpha · source 0.1.0</span><div class="io-strip"><span><b>Input</b>campaign, SUT, reference, tolerance</span><span aria-hidden="true">→</span><span><b>Output</b>records, reports, blockers, audit trail</span></div></div>
  </div>
</section>

## Role in one sentence

**Validation tests what SPM-Kit actually does from outside.** It is not merely
another internal unit-test directory.

## Problem it solves

An internal function can pass tests while packaging, CLI defaults, optional
dependencies or public execution behave differently. The validation repository
treats the installed `spmkit` executable as the system under test (SUT), captures
what it emits and compares only against a declared, frozen contract.

## What it does

- runs SPM-Kit with `subprocess` rather than importing its internals;
- freezes SUT/reference identities, data design, preprocessing, metrics and tolerances;
- records stdout, stderr, return code, timestamps and produced artifacts;
- retains manifests, result rows, summaries, locks, protocols and incident records;
- classifies reference independence separately from process isolation;
- preserves failures, blockers and limitations alongside passing results;
- publishes scoped campaign evidence without promoting it to universal validity.

## What it deliberately does not do

- change a tolerance after observing the result;
- infer a PASS where the campaign says `TODO-SCIENTIFIC-DECISION`;
- hide failed or inconclusive cases;
- call public experimental data physical ground truth;
- treat Gwyddion as an oracle for every AFM/SPM domain;
- establish reference independence merely by spawning another process.

## Black-box execution boundary

```text
frozen campaign
      ↓
isolated environment
      ↓
installed SPM-Kit package (system under test)
      ↓
public CLI / executable
      ↓
captured stdout, stderr and artifacts
      ↓
declared reference comparison
      ↓
evidence report + limitations + audit trail
```

The runner constructs `[executable, command, *arguments]`, applies the timeout,
and records the process outcome. Reference generation/comparison remains a
separate campaign concern.

## Installation

The package is not on PyPI. Its basic runner currently needs the source checkout;
synthetic campaigns also need the separate Phantoms checkout available to Python.

```bash
git clone https://github.com/kegouro/spmkit-validation.git
cd spmkit-validation
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
spmkit-validation --help
```

## First successful command

```bash
spmkit-validation --help
spmkit-validation report --help
```

The current CLI exposes `campaign` and `report`. A campaign run writes data, so
choose an explicit output directory and preserve it as evidence only after review.

## Campaign browser

The date shown is the first retained-summary commit date, not an inferred
experimental acquisition date.

| Campaign | Retained | Tested identity | Reference / independence | Cases and metrics | Frozen tolerance | Result | Level | Limitation / evidence |
|---|---|---|---|---|---|---|---|---|
| `gwyddion-roughness-48-v0.1` | 2026-07-19 | SPM-Kit `5a704d6`; Phantoms `622a888` | Gwyddion 2.71 native GSF/libgwyprocess route; external software with harness-authored execution | 48 float32-nm matrices; Sa, Sq, Sz; 144 comparisons | `abs(a-b) <= 1e-6 nm + 1e-6*max(abs(a),abs(b))`; no preprocessing | **144/144 within threshold** | `LEVEL 3` | shared matrices, not physical acquisition; [summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/gwyddion_roughness_48_v0.1_summary.json) |
| `real-data-roughness-pilot-v0.1` | 2026-07-19 | SPM-Kit `5a704d6` | Gwyddion 2.71; shared-matrix route cross-compared, parser routes observational | 12 public GWY records; 36 metric comparisons; 10 parser equivalences, 2 differences | same frozen metric threshold; no preprocessing | **36/36 shared-matrix** | `LEVEL 3` for metric route | public real data are not physical truth; [summary](https://github.com/kegouro/spmkit-validation/blob/main/evidence/campaigns/real_data_roughness_pilot_v0.1_summary.json) |
| `nanoscope-spm-parser-pilot-v0.1` | 2026-07-19 | limited parser implementation `06b0044` after freeze `5e22104` | Gwyddion 2.71; external confirmation was not blind after incident | 6 demonstrated Nanoscope III files; matrices + 18 Sa/Sq/Sz comparisons | frozen roughness threshold; matrix deltas observed | zero reported pixel delta; **18/18 within threshold** | `LEVEL 2` limited parser claim | `ACCIDENTAL_PRE_FREEZE_UNBLINDING`; [audit](https://github.com/kegouro/spmkit-validation/blob/main/docs/campaigns/nanoscope_spm_parser_pilot_v0.1_audit.md) |
| `gwyddion-cross-validation-v0.1` release milestone | 2026-07-27 | published SPM-Kit 0.1.4 wheel | installed Gwyddion 2.71 libraries; wrapper contains harness-authored Sa accumulation | 6 synthetic binary64 surfaces; 18 metric comparisons | published frozen budget | **18/18 conforming**; 8/8 independence-negative and 7/7 tamper tests retained | `LEVEL 3` | synthetic only; [tag](https://github.com/kegouro/spmkit-validation/tree/gwyddion-cross-validation-v0.1) |

The 20-case threshold calibration retained 60/60 comparisons under the accepted
candidate policy. It calibrates the policy; it is not another independent
physical campaign and is not added to the totals above.

## What a PASS means

A PASS means that, for the frozen SUT, inputs, command, preprocessing, metric,
reference route and tolerance, the recorded comparison met the campaign rule.
It enables only the narrow claim written in that campaign.

## What a PASS does not mean

A PASS does not establish:

- correctness of every SPM-Kit capability or every metric;
- parser support for every instrument variant;
- physical calibration or traceability;
- independence of a reference implementation unless separately argued;
- equivalence under different preprocessing/defaults;
- blind confirmation when an incident exposed the expected values;
- future-version behavior.

## Failures and blockers are evidence too

| Record | Public status | Why it remains visible |
|---|---|---|
| Smoke/full YAML definitions without promoted summaries | `LEVEL 0 — CLAIMED` as campaign results | executable configuration is not a retained validated outcome |
| Nanoscope external confirmation | `ACCIDENTAL_PRE_FREEZE_UNBLINDING` | the incident prevents a blind-holdout claim despite numerical agreement |
| Real-data parser track | observational, including two channel-count differences | no parser threshold was frozen; differences cannot be relabeled as passes |
| Missing physical and interlaboratory campaigns | blocker for general `LEVEL 4`/`LEVEL 5` | software and cross-reference evidence cannot substitute for them |

## Complete reproduction walkthrough: current smoke campaign

This walkthrough verifies the public campaign plumbing and produces a
descriptive report. It does **not** reproduce the retained Gwyddion evidence and
does not assign a scientific PASS.

### 1. Prepare isolated checkouts

```bash
git clone https://github.com/kegouro/spmkit.git
git clone https://github.com/kegouro/spmkit-phantoms.git
git clone https://github.com/kegouro/spmkit-validation.git

python -m venv validation-env
source validation-env/bin/activate
python -m pip install -e ./spmkit
python -m pip install -e ./spmkit-phantoms
python -m pip install -e ./spmkit-validation
```

Record all three commits and `spmkit --version` before execution.

### 2. Run through the public installed CLI

```bash
spmkit-validation campaign \
  spmkit-validation/campaigns/smoke_v0.1.yaml \
  validation-runs/ \
  --spmkit "$(command -v spmkit)"
```

Expected high-level output: six cases from inclined, sine and step surfaces,
each clean and with low Gaussian noise.

### 3. Inspect the run

```text
validation-runs/smoke_v0.1/
├── phantoms/          clean/observed bundles and manifests
├── runs/              captured stdout/stderr and SPM-Kit outputs
└── cases.csv          ground truth, observed values and differences
```

`cases.csv` deliberately labels evaluated rows `TODO-SCIENTIFIC-DECISION`. The
campaign definition does not contain a promoted tolerance policy.

### 4. Generate the descriptive report

```bash
spmkit-validation report \
  validation-runs/smoke_v0.1/cases.csv \
  validation-runs/smoke-report/
```

This creates `report.md` and diagnostic figures. Review the captured streams,
manifests and numerical differences before preserving the directory. Do not
rename the descriptive report as cross-validation evidence.

## Inputs, outputs and audit trail

| Input | Captured output | Audit value |
|---|---|---|
| campaign YAML/protocol | resolved cases and generated inputs | exact scope and parameter intent |
| installed executable path/identity | command vectors, stdout, stderr, return codes | public behavior and environment failure evidence |
| reference route | reference outputs and independence classification | basis of comparison |
| frozen tolerance | per-metric comparison rows | makes PASS/FAIL reviewable |
| lock/manifest/checksums | retained identities | detects later drift or tampering |
| limitation/incident record | visible caveat beside result | prevents overpromotion |

## Architecture and integrations

- **Validation → Core:** implemented subprocess boundary using public CLI behavior.
- **Phantoms → Validation:** implemented for synthetic YAML campaigns; the
  exact Phantoms revision must be frozen.
- **Data Hunter → Validation:** human-reviewed manual handoff only.
- **Gwyddion → Validation:** present only in declared protocols/campaigns.
- **Fathom → Validation:** no general GUI automation claim; numerical campaigns
  test public package surfaces instead.

## Scientific status and limitations

The repository contains scoped `LEVEL 2` and `LEVEL 3` evidence described above.
No current record establishes a general `LEVEL 4` or `LEVEL 5` claim.

- Process isolation is not proof of conceptual or implementation independence.
- Synthetic matrices do not include physical acquisition uncertainty.
- The reusable package CLI is young and not the only path used by historical retained campaigns.
- Full campaigns write evidence and require explicit review/retention policy.
- Tolerances, references and software identities must remain immutable after freeze.

## Contribute

High-value proposals define one mensurand, lawful/frozen inputs, reference
independence, tolerance before execution, failure handling and an honest limit.
Use the repository's campaign and independent-comparison issue forms.

[Repository](https://github.com/kegouro/spmkit-validation) ·
[Authoritative campaign matrix](https://github.com/kegouro/spmkit-validation/blob/main/docs/CAMPAIGNS.md) ·
[Workflow: independent cross-comparison](workflows/index.md#workflow-d-build-an-independent-cross-comparison) ·
[Next: artifact contracts](contracts.md)
