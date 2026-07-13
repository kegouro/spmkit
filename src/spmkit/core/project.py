"""Proyecto ``.spmproj`` — estado mínimo de sesión, versionado y tolerante.

Guarda **qué archivos están abiertos** y la **receta/parámetros activos** (el estado
analítico básico), no el layout de docks ni preferencias complejas (eso es F4). Es JSON
plano y versionado: al leer, ignora campos desconocidos y rellena los que falten, para
que un ``.spmproj`` viejo abra en una versión nueva sin romperse.

Puro: no sabe de UI. La GUI arma el :class:`ProjectState` y lo consume.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Versión del esquema ``.spmproj``. Bump si cambia de forma incompatible.
PROJECT_VERSION = 1


@dataclass
class OpenFile:
    """Un archivo abierto en la sesión: su ruta y cómo se abrió (image/force)."""

    path: str
    kind: str  # "image" | "force"
    sha256: str | None = None

    @classmethod
    def from_path(cls, path: str | Path, kind: str) -> OpenFile:
        ruta = Path(path)
        resumen = hashlib.sha256()
        with ruta.open("rb") as flujo:
            for bloque in iter(lambda: flujo.read(1024 * 1024), b""):
                resumen.update(bloque)
        return cls(path=str(ruta), kind=kind, sha256=resumen.hexdigest())


@dataclass
class ProjectState:
    """Estado mínimo de un proyecto: archivos abiertos + parámetros de análisis."""

    files: list[OpenFile] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)  # receta/ajuste activo (genérico)
    perspective: str = "force"
    version: int = PROJECT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "perspective": self.perspective,
            "files": [
                {"path": f.path, "kind": f.kind, "sha256": f.sha256} for f in self.files
            ],
            "params": self.params,
        }


def save_project(state: ProjectState, path: str | Path) -> Path:
    """Escribe el proyecto a ``path`` (JSON). Devuelve la ruta."""
    out = Path(path)
    out.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def load_project(path: str | Path) -> ProjectState:
    """Lee un ``.spmproj``, tolerante a campos faltantes/desconocidos."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    files = [
        OpenFile(
            path=str(f["path"]),
            kind=str(f.get("kind", "force")),
            sha256=str(f["sha256"]) if f.get("sha256") is not None else None,
        )
        for f in raw.get("files", [])
        if isinstance(f, dict) and f.get("path")
    ]
    return ProjectState(
        files=files,
        params=dict(raw.get("params", {})),
        perspective=str(raw.get("perspective", "force")),
        version=int(raw.get("version", PROJECT_VERSION)),
    )
