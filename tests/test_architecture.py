"""Test de arquitectura: la separación de 3 capas se hace cumplir como código.

`core/` es Python puro **sin imports de UI**. Este test recorre cada módulo de `core/`
con el AST y falla si alguno importa un toolkit de interfaz. No depende de disciplina
humana: CI lo hace fallar. Sólo usa la stdlib, así que corre en cualquier entorno.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "spmkit"
_CORE = _SRC / "core"

#: Toolkits de UI que jamás deben aparecer en ``core/``.
_FORBIDDEN = {"PyQt6", "PyQt5", "PySide6", "PySide2", "pyqtgraph"}


def _top_level_imports(pyfile: Path) -> set[str]:
    tree = ast.parse(pyfile.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_core_has_no_ui_imports() -> None:
    offenders = []
    for pyfile in _CORE.rglob("*.py"):
        forbidden = _top_level_imports(pyfile) & _FORBIDDEN
        if forbidden:
            offenders.append(f"{pyfile.relative_to(_SRC)}: importa {', '.join(sorted(forbidden))}")
    assert not offenders, "core/ no debe importar UI:\n" + "\n".join(offenders)
