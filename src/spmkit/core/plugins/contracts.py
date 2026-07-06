"""Contratos versionados del sistema de plugins — ``spmkit.plugins.v1``.

Son ``typing.Protocol``s (contratos de comportamiento) + un dataclass de metadatos.
Se escriben **primero**: todo lo demás depende de ellos, y su estabilidad protege a las
extensiones de terceros (como los drivers de Napalm o las extensiones de VS Code). Un
cambio incompatible obliga a un ``v2`` con compatibilidad hacia atrás.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

#: Versión del contrato de plugins (bump → nuevo grupo de entry-points).
PLUGIN_API_VERSION = "1"

#: Grupo de entry-points que descubre el registry.
ENTRY_POINT_GROUP = "spmkit.plugins.v1"

#: Tipo de dato que un archivo puede contener. Un QI de JPK es ``("image", "force")``.
Kind = Literal["image", "force"]


@dataclass(frozen=True)
class DatasetInfo:
    """Metadatos de un archivo **sin cargar los datos pesados** (para ``Reader.inspect``).

    Permite a la UI preguntar "¿qué hay aquí?" y —si hay varios ``kinds``— ofrecer abrir
    como *Imagen* o *Mapa de curvas* antes de leer los megabytes.
    """

    path: Path
    format: str  # etiqueta del formato, p. ej. "nid", "jpk-force"
    kinds: tuple[Kind, ...]  # p. ej. ("image",) o ("image", "force")
    channels: tuple[str, ...] = ()
    grid_shape: tuple[int, int] | None = None  # filas×cols para force-volume
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Reader(Protocol):
    """Lector de un formato de archivo.

    ``inspect`` es **barato** (solo cabecera); ``load`` carga el ``kind`` pedido (o el
    primero declarado). ``extensions`` son minúsculas con punto (``".nid"``).
    """

    extensions: tuple[str, ...]

    def inspect(self, path: str | Path) -> DatasetInfo: ...

    def load(self, path: str | Path, kind: Kind | None = None) -> Any: ...


@runtime_checkable
class Analysis(Protocol):
    """Análisis/operación registrable (para F3+). Contrato mínimo estable."""

    name: str
    kinds: tuple[Kind, ...]


@runtime_checkable
class Domain(Protocol):
    """Una física/dominio completo (Fathom = AFM). Se auto-registra en el host.

    El host itera ``readers``/``analyses`` para poblar sus registries sin conocer el
    dominio concreto.
    """

    name: str
    readers: tuple[Reader, ...]
    perspectives: tuple[str, ...]
