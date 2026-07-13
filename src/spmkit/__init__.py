"""spmkit: analizador open-source de datos AFM/KPFM para SPM.

API de conveniencia de nivel superior::

    from spmkit import load
    data = load("scan.nid")
    ch = data["Z-Axis"]

Para el análisis usa los submódulos de :mod:`spmkit.core.analysis`.
"""

from importlib.metadata import PackageNotFoundError, version

from spmkit.core import SPMChannel, SPMData, load

try:
    __version__ = version("spmkit")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["load", "SPMData", "SPMChannel", "__version__"]
