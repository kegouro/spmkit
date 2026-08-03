"""Static audit primitives for conservative Gwyddion source migration work."""

from spmkit.compat.gwyddion.profiles import (
    GwyddionCompatibilityProfile,
    GwyddionVersion,
    gwyddion_2_71_profile,
)
from spmkit.compat.gwyddion.reports import (
    GwyddionModuleAuditReport,
    canonical_report_json,
    report_from_dict,
    report_to_dict,
)
from spmkit.compat.gwyddion.source_audit import audit_gwyddion_source

__all__ = [
    "GwyddionCompatibilityProfile",
    "GwyddionModuleAuditReport",
    "GwyddionVersion",
    "audit_gwyddion_source",
    "canonical_report_json",
    "gwyddion_2_71_profile",
    "report_from_dict",
    "report_to_dict",
]
