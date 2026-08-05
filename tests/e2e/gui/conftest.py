"""Fixtures compartidas de los tests E2E de GUI (journey de imagen).

Mismo patrón que ``tests/gui/conftest.py``: si el entorno no tiene el stack de GUI
(PyQt6 + pytest-qt), se omite esta carpeta en la colección en vez de fallar al
importar. Con el extra ``gui`` instalado (job de CI dedicado), corren normalmente.
"""

from __future__ import annotations

try:
    import PyQt6  # noqa: F401
    import pytestqt  # noqa: F401

    _HAS_GUI = True
except ImportError:  # pragma: no cover - CI sin extra gui
    _HAS_GUI = False

#: Sin el stack de GUI, pytest ignora los ``test_*.py`` de esta carpeta.
collect_ignore_glob = [] if _HAS_GUI else ["test_*.py"]
