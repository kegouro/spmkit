"""Backend de spmkit: puro Python, sin dependencias de UI.

Reúne las cuatro sub-capas del núcleo:

* :mod:`spmkit.core.io` — lectura de formatos (``.nid``, ``.nhf``)
* :mod:`spmkit.core.models` — modelos de datos del dominio
* :mod:`spmkit.core.analysis` — análisis numérico
* :mod:`spmkit.core.export` — exportación a formatos abiertos
"""

from spmkit.core import analysis, export, io, models
from spmkit.core.io import load
from spmkit.core.models import SPMChannel, SPMData

__all__ = ["io", "models", "analysis", "export", "load", "SPMData", "SPMChannel"]
