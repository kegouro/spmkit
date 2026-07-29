---
title: Artifact and data contracts
description: Honest implemented, manual, planned, and conceptual handoffs between SPM-Kit ecosystem components.
---

# Artifact and data contracts

These contracts describe what actually crosses repository boundaries. They do
not imply automation where a human decision is required.

| Producer | Artifact | Consumer | Contract | Status | Scientific purpose |
|---|---|---|---|---|---|
| SPM-Kit Core | `SPMData`, `SPMChannel`, `ForceCurve`, `ForceVolume`, typed results | Fathom | in-process public Python objects | **implemented** | one numerical implementation across CLI/API/GUI |
| Core CLI | CSV/JSON, figures, maps, reports and console output | researcher / Validation | command-specific public artifacts | **implemented, path-specific** | reproducible headless execution and capture |
| Fathom | `.spmproj`, result JSON, map CSV, figures, reports where enabled | researcher / Core follow-up | project and export actions | **implemented, route-specific** | preserve interactive choices and outputs |
| Phantoms | `clean.npz`, `manifest.json` | Core / Validation | `z_data`, X/Y size, Z unit, model, canonical hashes | **implemented** | known clean numerical truth |
| Phantoms | `observed.npz`, masks, `corruption_manifest.json` | Core / Validation | clean/observed separation, order, parameters, seed, hashes | **implemented** | controlled recovery and corruption tests |
| Validation | `cases.csv`, captured stdout/stderr, reports, summaries, locks | researchers / site | campaign-specific retained evidence | **implemented** | audit a narrow external claim |
| Data Hunter | SQLite catalog, campaign store, JSON/JSONL/CSV/Markdown views | human reviewer | normalized records, file inventories, source provenance | **implemented** | prioritize and audit candidate evidence |
| Human reviewer | accepted native file + lawful provenance | Core reader test | manual fixture selection | **documented manual handoff** | parser/channel/orientation test |
| Human reviewer | accepted data/reference proposal | Validation | mensurand, rights, reference, tolerance and independence review | **documented manual handoff** | design an external campaign |
| Data Hunter | automatic benchmark feed | Validation | none | **planned, not implemented** | future reviewed manifest integration |
| Fathom | universally portable recipe for every perspective | external automation | no uniform current contract | **conceptual only** | future reproducible GUI-to-headless handoff |

## Core domain contract

At the numerical boundary, preserve:

- array values and shape;
- physical unit and X/Y field of view;
- channel name, group and scan direction;
- force segment kind/direction and calibration when present;
- source metadata needed to interpret the result;
- preprocessing and model parameters outside the data object when the result
  type does not carry them completely.

## Phantom bundle contract

Canonical array SHA-256 identifies normalized dtype, shape and bytes. Artifact
SHA-256 identifies the compressed file. Manifest SHA-256 identifies normalized
metadata. None of these hashes asserts physical validity or authenticity.

## Validation evidence contract

A retained campaign needs the system under test, public command, input
identities, reference route, independence classification, metrics, tolerance,
environment, outputs, result, failures/incidents and limitations. A generated
report without those fields is descriptive output, not promoted evidence.

## Data Hunter review contract

Candidate records stay candidates until a person checks scientific relevance,
native/processed relationship, methods, calibration, license/redistribution,
privacy, integrity and intended role. Rejection is a valid review outcome.

[Run a workflow](workflows/index.md) · [Return to ecosystem overview](index.md)
