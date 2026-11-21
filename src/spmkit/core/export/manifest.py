"""Manifiesto de ejecución reproducible para trazabilidad.

Este módulo define las estructuras de datos para emitir un comprobante
de ejecución (provenance) sin filtrar información sensible del entorno.
"""

from __future__ import annotations

import datetime
import hashlib
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.export.writers import _to_serializable


def _get_git_commit() -> str | None:
    """Intenta recuperar el hash del commit actual de Git, si está disponible limpiamente."""
    try:
        # Solo ejecutamos git si el directorio .git existe para evitar errores o delays
        git_dir = Path(__file__).resolve().parents[4] / ".git"
        if not git_dir.exists():
            return None
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(git_dir.parent),
            timeout=1.0,
        )
        return res.stdout.strip()
    except Exception:
        return None


def _get_file_hash(path: Path) -> str:
    """Calcula el SHA-256 de un archivo en disco."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class EnvironmentInfo:
    python_version: str
    numpy_version: str
    platform: str

    @classmethod
    def capture(cls) -> EnvironmentInfo:
        return cls(
            python_version=sys.version.split(" ")[0],
            numpy_version=np.__version__,
            platform=platform.platform(),
        )


@dataclass
class RunManifest:
    """Estructura del manifiesto de ejecución reproducible."""

    input_file: str
    input_sha256: str
    input_bytes: int
    command: str
    args: dict[str, Any]
    channel: str
    leveling_method: str
    units: str
    results_produced: list[str]
    warnings: list[str]
    status: str
    duration_seconds: float

    schema_version: str = "1.0"
    spmkit_name: str = "SPM-Kit"
    spmkit_version: str = field(
        default_factory=lambda: (getattr(sys.modules.get("spmkit"), "__version__", "unknown"))
    )
    git_commit: str | None = field(default_factory=_get_git_commit)
    timestamp_utc: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat()
    )
    environment: EnvironmentInfo = field(default_factory=EnvironmentInfo.capture)

    @classmethod
    def create(
        cls,
        input_path: Path,
        command: str,
        args: dict[str, Any],
        channel: str,
        leveling_method: str,
        units: str,
        results_produced: list[str],
        warnings: list[str],
        status: str,
        duration_seconds: float,
    ) -> RunManifest:
        """Crea el manifiesto obteniendo la meta-información del archivo."""
        if not input_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {input_path}")

        return cls(
            input_file=input_path.name,  # Guardamos solo el basename (portable)
            input_sha256=_get_file_hash(input_path),
            input_bytes=input_path.stat().st_size,
            command=command,
            args=args,
            channel=channel,
            leveling_method=leveling_method,
            units=units,
            results_produced=results_produced,
            warnings=warnings,
            status=status,
            duration_seconds=duration_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        """Devuelve un diccionario listo para JSON."""
        return dict(_to_serializable(asdict(self)))
