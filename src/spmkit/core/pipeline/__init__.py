"""Motor de pipeline reproducible de spmkit (``Recipe`` + operaciones + ``run``)."""

from spmkit.core.pipeline.operations import available_operations, get_operation, operation
from spmkit.core.pipeline.recipe import Recipe, Step, evaluate_condition
from spmkit.core.pipeline.run import ProgressCallback, run

__all__ = [
    "Recipe",
    "Step",
    "evaluate_condition",
    "operation",
    "get_operation",
    "available_operations",
    "run",
    "ProgressCallback",
]
