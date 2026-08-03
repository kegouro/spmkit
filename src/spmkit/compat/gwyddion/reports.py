"""Deterministic JSON-compatible models for static Gwyddion source audits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from spmkit.compat.gwyddion.profiles import GwyddionCompatibilityProfile, GwyddionVersion
from spmkit.compat.gwyddion.symbols import (
    DependencyReference,
    IncludeReference,
    ModuleRegistration,
    RegistrationKind,
    SourceLocation,
    SourceSpan,
    SymbolClassification,
    SymbolReference,
    SymbolSupportStatus,
)

REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AuditEvidence:
    """Static-audit provenance and limitations, without an execution claim."""

    source_sha256: str
    scanner: str
    scanner_version: int
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class GwyddionModuleAuditReport:
    """Immutable report from a lexical Gwyddion C source inventory."""

    schema_version: int
    module_path: str | None
    content_sha256: str
    profile: GwyddionCompatibilityProfile
    evidence: AuditEvidence
    registrations: tuple[ModuleRegistration, ...]
    includes: tuple[IncludeReference, ...]
    gwyddion_symbols: tuple[SymbolReference, ...]
    gtk_glib_dependencies: tuple[DependencyReference, ...]
    mapped_total: int
    adapter_required_total: int
    unsupported_total: int
    unknown_total: int
    has_ui_dependency: bool
    likely_selection_dependencies: tuple[str, ...]
    likely_parameter_system_dependencies: tuple[str, ...]
    likely_publication_logging_dependencies: tuple[str, ...]
    conservative_mutation_hints: tuple[str, ...]
    migration_blockers: tuple[str, ...]
    migration_warnings: tuple[str, ...]
    evidence_limitations: tuple[str, ...]


def _location_to_dict(location: SourceLocation) -> dict[str, object]:
    return {"column": location.column, "line": location.line, "source_path": location.source_path}


def _span_to_dict(span: SourceSpan) -> dict[str, object]:
    return {"end": _location_to_dict(span.end), "start": _location_to_dict(span.start)}


def _profile_to_dict(profile: GwyddionCompatibilityProfile) -> dict[str, object]:
    return {
        "exact_symbol_mappings": [list(item) for item in profile.exact_symbol_mappings],
        "glib_symbol_prefixes": list(profile.glib_symbol_prefixes),
        "gwyddion_symbol_prefixes": list(profile.gwyddion_symbol_prefixes),
        "gtk_symbol_prefixes": list(profile.gtk_symbol_prefixes),
        "name": profile.name,
        "registration_calls": list(profile.registration_calls),
        "version": {
            "major": profile.version.major,
            "minor": profile.version.minor,
            "patch": profile.version.patch,
        },
    }


def report_to_dict(report: GwyddionModuleAuditReport) -> dict[str, object]:
    """Return a JSON-compatible, order-preserving representation of an audit report."""
    return {
        "adapter_required_total": report.adapter_required_total,
        "content_sha256": report.content_sha256,
        "conservative_mutation_hints": list(report.conservative_mutation_hints),
        "evidence": {
            "limitations": list(report.evidence.limitations),
            "scanner": report.evidence.scanner,
            "scanner_version": report.evidence.scanner_version,
            "source_sha256": report.evidence.source_sha256,
        },
        "evidence_limitations": list(report.evidence_limitations),
        "gtk_glib_dependencies": [
            {
                "classification": dependency.classification.value,
                "name": dependency.name,
                "occurrences": [_span_to_dict(span) for span in dependency.occurrences],
                "support_status": dependency.support_status.value,
            }
            for dependency in report.gtk_glib_dependencies
        ],
        "gwyddion_symbols": [
            {
                "call_occurrences": [_span_to_dict(span) for span in symbol.call_occurrences],
                "classification": symbol.classification.value,
                "occurrences": [_span_to_dict(span) for span in symbol.occurrences],
                "support_status": symbol.support_status.value,
                "symbol": symbol.symbol,
            }
            for symbol in report.gwyddion_symbols
        ],
        "has_ui_dependency": report.has_ui_dependency,
        "includes": [
            {
                "is_local": include.is_local,
                "name": include.name,
                "span": _span_to_dict(include.span),
            }
            for include in report.includes
        ],
        "likely_parameter_system_dependencies": list(report.likely_parameter_system_dependencies),
        "likely_publication_logging_dependencies": list(
            report.likely_publication_logging_dependencies
        ),
        "likely_selection_dependencies": list(report.likely_selection_dependencies),
        "mapped_total": report.mapped_total,
        "migration_blockers": list(report.migration_blockers),
        "migration_warnings": list(report.migration_warnings),
        "module_path": report.module_path,
        "registrations": [
            {
                "callee": registration.callee,
                "declared_name": registration.declared_name,
                "kind": registration.kind.value,
                "span": _span_to_dict(registration.span),
            }
            for registration in report.registrations
        ],
        "profile": _profile_to_dict(report.profile),
        "schema_version": report.schema_version,
        "unknown_total": report.unknown_total,
        "unsupported_total": report.unsupported_total,
    }


def canonical_report_json(report: GwyddionModuleAuditReport) -> str:
    """Serialize a report deterministically without writing a file."""
    return json.dumps(
        report_to_dict(report),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _location_from_dict(value: dict[str, Any]) -> SourceLocation:
    return SourceLocation(value["source_path"], int(value["line"]), int(value["column"]))


def _span_from_dict(value: dict[str, Any]) -> SourceSpan:
    return SourceSpan(_location_from_dict(value["start"]), _location_from_dict(value["end"]))


def _profile_from_dict(value: dict[str, Any]) -> GwyddionCompatibilityProfile:
    version = value["version"]
    return GwyddionCompatibilityProfile(
        name=str(value["name"]),
        version=GwyddionVersion(
            int(version["major"]),
            int(version["minor"]),
            int(version["patch"]),
        ),
        registration_calls=tuple(str(item) for item in value["registration_calls"]),
        gwyddion_symbol_prefixes=tuple(str(item) for item in value["gwyddion_symbol_prefixes"]),
        gtk_symbol_prefixes=tuple(str(item) for item in value["gtk_symbol_prefixes"]),
        glib_symbol_prefixes=tuple(str(item) for item in value["glib_symbol_prefixes"]),
        exact_symbol_mappings=tuple(
            (str(item[0]), str(item[1])) for item in value["exact_symbol_mappings"]
        ),
    )


def report_from_dict(value: dict[str, Any]) -> GwyddionModuleAuditReport:
    """Reconstruct a report from :func:`report_to_dict` output."""
    evidence_value = value["evidence"]
    return GwyddionModuleAuditReport(
        schema_version=int(value["schema_version"]),
        module_path=value["module_path"],
        content_sha256=str(value["content_sha256"]),
        profile=_profile_from_dict(value["profile"]),
        evidence=AuditEvidence(
            source_sha256=str(evidence_value["source_sha256"]),
            scanner=str(evidence_value["scanner"]),
            scanner_version=int(evidence_value["scanner_version"]),
            limitations=tuple(str(item) for item in evidence_value["limitations"]),
        ),
        registrations=tuple(
            ModuleRegistration(
                kind=RegistrationKind(item["kind"]),
                callee=str(item["callee"]),
                declared_name=item["declared_name"],
                span=_span_from_dict(item["span"]),
            )
            for item in value["registrations"]
        ),
        includes=tuple(
            IncludeReference(
                name=str(item["name"]),
                is_local=bool(item["is_local"]),
                span=_span_from_dict(item["span"]),
            )
            for item in value["includes"]
        ),
        gwyddion_symbols=tuple(
            SymbolReference(
                symbol=str(item["symbol"]),
                classification=SymbolClassification(item["classification"]),
                support_status=SymbolSupportStatus(item["support_status"]),
                occurrences=tuple(_span_from_dict(span) for span in item["occurrences"]),
                call_occurrences=tuple(_span_from_dict(span) for span in item["call_occurrences"]),
            )
            for item in value["gwyddion_symbols"]
        ),
        gtk_glib_dependencies=tuple(
            DependencyReference(
                name=str(item["name"]),
                classification=SymbolClassification(item["classification"]),
                support_status=SymbolSupportStatus(item["support_status"]),
                occurrences=tuple(_span_from_dict(span) for span in item["occurrences"]),
            )
            for item in value["gtk_glib_dependencies"]
        ),
        mapped_total=int(value["mapped_total"]),
        adapter_required_total=int(value["adapter_required_total"]),
        unsupported_total=int(value["unsupported_total"]),
        unknown_total=int(value["unknown_total"]),
        has_ui_dependency=bool(value["has_ui_dependency"]),
        likely_selection_dependencies=tuple(
            str(item) for item in value["likely_selection_dependencies"]
        ),
        likely_parameter_system_dependencies=tuple(
            str(item) for item in value["likely_parameter_system_dependencies"]
        ),
        likely_publication_logging_dependencies=tuple(
            str(item) for item in value["likely_publication_logging_dependencies"]
        ),
        conservative_mutation_hints=tuple(
            str(item) for item in value["conservative_mutation_hints"]
        ),
        migration_blockers=tuple(str(item) for item in value["migration_blockers"]),
        migration_warnings=tuple(str(item) for item in value["migration_warnings"]),
        evidence_limitations=tuple(str(item) for item in value["evidence_limitations"]),
    )
