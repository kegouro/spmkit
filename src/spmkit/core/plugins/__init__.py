"""Sistema de plugins/extensiones de spmkit (host multi-física).

`spmkit` es el *host*; los dominios (p. ej. **Fathom** para AFM) registran lectores,
análisis y paneles vía los contratos versionados de :mod:`spmkit.core.plugins.contracts`
(grupo de entry-points ``spmkit.plugins.v1``). El host nunca conoce los dominios: se
auto-registran. Ver ``docs/design/ROADMAP.md`` §3.
"""

from spmkit.core.plugins.contracts import (
    ENTRY_POINT_GROUP,
    PLUGIN_API_VERSION,
    Analysis,
    DatasetInfo,
    Domain,
    Kind,
    Reader,
)
from spmkit.core.plugins.registry import (
    reader_for,
    readers,
    register_reader,
    supported_extensions,
)

__all__ = [
    "PLUGIN_API_VERSION",
    "ENTRY_POINT_GROUP",
    "Kind",
    "DatasetInfo",
    "Reader",
    "Analysis",
    "Domain",
    "register_reader",
    "readers",
    "reader_for",
    "supported_extensions",
]
