"""spmkit: analizador open-source de datos AFM/KPFM para SPM.

API de conveniencia de nivel superior::

    from spmkit import load
    data = load("scan.nid")
    ch = data["Z-Axis"]

Para el análisis usa los submódulos de :mod:`spmkit.core.analysis`.
"""

from spmkit.core import SPMChannel, SPMData, load

__version__ = "0.1.0"

__all__ = ["load", "SPMData", "SPMChannel", "__version__"]
