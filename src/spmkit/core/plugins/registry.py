"""Registry de lectores en proceso + descubrimiento de plugins por entry-points.

Registra los lectores *built-in* (Fathom/AFM) y cualquier extensión de terceros que
declare el grupo :data:`~spmkit.core.plugins.contracts.ENTRY_POINT_GROUP`. El
descubrimiento es perezoso e idempotente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spmkit.core.plugins.contracts import ENTRY_POINT_GROUP, Reader

_READERS: list[Reader] = []
_discovered = False


def register_reader(reader: Reader) -> None:
    """Añade un lector al registry (idempotente por identidad)."""
    if reader not in _READERS:
        _READERS.append(reader)


def readers() -> tuple[Reader, ...]:
    """Todos los lectores registrados (built-in + plugins)."""
    _ensure_discovered()
    return tuple(_READERS)


def reader_for(path: str | Path) -> Reader | None:
    """El lector que maneja la extensión de ``path`` (o ``None``)."""
    _ensure_discovered()
    ext = Path(path).suffix.lower()
    return next((r for r in _READERS if ext in r.extensions), None)


def supported_extensions() -> tuple[str, ...]:
    """Extensiones que algún lector registrado sabe leer."""
    _ensure_discovered()
    return tuple(sorted({e for r in _READERS for e in r.extensions}))


def _ensure_discovered() -> None:
    global _discovered
    if _discovered:
        return
    _discovered = True  # antes de registrar, para no recursar
    _register_builtins()
    _discover_entry_points()


def _register_builtins() -> None:
    from spmkit.core.io.readers import BUILTIN_READERS

    for reader in BUILTIN_READERS:
        register_reader(reader)
    _register_afmformats()


def _register_afmformats() -> None:
    """Registra el lector de afmformats si el extra ``afm`` está instalado (check barato)."""
    from importlib.util import find_spec

    if find_spec("afmformats") is None:
        return
    from spmkit.core.io.afmformats_reader import AfmformatsReader

    register_reader(AfmformatsReader())


def _discover_entry_points() -> None:
    """Registra plugins declarados en ``spmkit.plugins.v1`` (tolerante a fallos)."""
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - Python <3.8 no soportado
        return
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception:  # noqa: BLE001 - metadata rara/vieja: sin plugins, no rompas
        return
    for ep in eps:
        try:
            _register_object(ep.load())
        except Exception:  # noqa: BLE001 - un plugin roto no tumba al host
            continue


def _register_object(obj: Any) -> None:
    """Registra un objeto de plugin: Domain (tiene ``readers``), Reader, o callable."""
    if hasattr(obj, "readers"):  # Domain
        for reader in obj.readers:
            register_reader(reader)
    elif hasattr(obj, "extensions"):  # Reader
        register_reader(obj)
    elif callable(obj):  # función de registro
        obj()
