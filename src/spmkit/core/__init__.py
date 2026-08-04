"""Backend de spmkit: puro Python, sin dependencias de UI.

Reúne las cuatro sub-capas del núcleo:

* :mod:`spmkit.core.io` — lectura de formatos (``.nid``, ``.nhf``)
* :mod:`spmkit.core.models` — modelos de datos del dominio
* :mod:`spmkit.core.analysis` — análisis numérico
* :mod:`spmkit.core.export` — exportación a formatos abiertos
"""

from spmkit.core import analysis, batch, export, io, models, viz
from spmkit.core.io import load
from spmkit.core.models import SPMChannel, SPMData
from spmkit.core.registry import (
    CapabilitySpec,
    ParameterSpec,
    filter_operations,
    get_operation,
    list_operations,
    resolve_callable,
)
from spmkit.core.verify import NidTrace, trace_nid

__all__ = [
    "io",
    "models",
    "analysis",
    "export",
    "viz",
    "batch",
    "load",
    "SPMData",
    "CapabilitySpec",
    "ParameterSpec",
    "get_operation",
    "list_operations",
    "filter_operations",
    "resolve_callable",
    "SPMChannel",
    "trace_nid",
    "NidTrace",
]
