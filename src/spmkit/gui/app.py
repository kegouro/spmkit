"""Punto de entrada de la GUI de spmkit — el default es **Fathom**.

``spmkit gui`` lanza el workspace Fathom (rediseño). La app clásica de 7 pestañas se
conserva en :mod:`spmkit.gui.legacy` y se lanza con ``spmkit gui --legacy``.
"""

from __future__ import annotations

from pathlib import Path


def run(open_path: str | Path | None = None) -> int:
    """Lanza el workspace Fathom (abre ``open_path`` si se indica)."""
    from spmkit.gui.app_workspace import run as run_fathom

    return run_fathom(open_path)


if __name__ == "__main__":
    raise SystemExit(run())
