"""Replay independently annotated force steps with original sample indices."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

from spmkit import __version__
from spmkit.core.analysis.force_steps import measure_force_step
from spmkit.core.export.manifest import file_sha256, get_git_commit
from spmkit.core.io import load_any
from spmkit.core.models import ForceVolume


def analyze_step_annotations(table: Path) -> Iterator[dict[str, Any]]:
    """Yield a measurement or an explicit failure for every annotation."""

    @lru_cache(maxsize=1)
    def load_source(path: Path) -> tuple[str, ForceVolume]:
        digest = file_sha256(path)
        volume, _ = load_any(path, "force")
        return digest, volume

    fields = ("source", "curve", "branch", "cycle", "boundary", "window")
    revision = get_git_commit()
    with table.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or sorted(reader.fieldnames) != sorted(fields):
            raise ValueError(f"Columnas requeridas: {', '.join(fields)}")
        for number, row in enumerate(reader, start=1):
            record: dict[str, Any] = {
                "annotation": number,
                "method": "local-linear-force-step-v1",
                "spmkit_version": __version__,
                "git_commit": revision,
                **{key: row[key] for key in fields},
            }
            try:
                if None in row or not all(row.values()):
                    raise ValueError("Fila incompleta o con campos adicionales")
                curve, cycle, boundary, window = (
                    int(row[k]) for k in ("curve", "cycle", "boundary", "window")
                )
                branch = row["branch"]
                if branch not in ("extend", "retract") or cycle < 0:
                    raise ValueError("Se requiere extend/retract y ciclo no negativo")
                digest, volume = load_source(table.parent / row["source"])
                record["source_sha256"] = digest
                segment = volume.curve(curve).segment(
                    cast(Literal["extend", "retract"], branch), cycle
                )
                if segment is None:
                    raise ValueError("Segmento o ciclo ausente")
                record.update(
                    asdict(measure_force_step(segment, boundary, window)), status="measured"
                )
            except Exception as exc:  # one rejected annotation must not remove other observations
                record.update(status="rejected", reason=f"{type(exc).__name__}: {exc}")
            yield record
