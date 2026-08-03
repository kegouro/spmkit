"""Dependency-free lexical inventory for conservative Gwyddion C source audits.

This module is intentionally not a complete C parser.  It never preprocesses,
compiles, executes, or loads the audited source.
"""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Iterable

from spmkit.compat.gwyddion.errors import InvalidGwyddionSourceError
from spmkit.compat.gwyddion.profiles import (
    GwyddionCompatibilityProfile,
    gwyddion_2_71_profile,
)
from spmkit.compat.gwyddion.reports import (
    REPORT_SCHEMA_VERSION,
    AuditEvidence,
    GwyddionModuleAuditReport,
)
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

_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_INCLUDE = re.compile(r'(?m)^[ \t]*#[ \t]*include[ \t]*([<"])([^>"]+)[>"]')
_KNOWN_REGISTRATION_KINDS = {
    "gwy_curve_map_func_register": RegistrationKind.CURVE_MAP,
    "gwy_file_func_register": RegistrationKind.FILE,
    "gwy_graph_func_register": RegistrationKind.GRAPH,
    "gwy_layer_func_register": RegistrationKind.LAYER,
    "gwy_process_func_register": RegistrationKind.PROCESS,
    "gwy_tool_func_register": RegistrationKind.TOOL,
    "gwy_volume_func_register": RegistrationKind.VOLUME,
    "gwy_xyz_func_register": RegistrationKind.XYZ,
}
_PROCESS_NUMERICAL_PREFIXES = (
    "gwy_data_field_area_",
    "gwy_data_field_filter_",
    "gwy_data_field_elliptic_",
    "gwy_data_field_grains_",
)
_MUTATING_DATA_FIELD_MARKERS = ("_set_", "_add_", "_subtract_", "_fill", "_filter_")
_LIMITATIONS = (
    "Lexical inventory only; this is not a complete C parser.",
    "No preprocessing, macro expansion, type resolution, or control-flow analysis occurs.",
    "Mutation, UI, selection, parameter, and publication findings are audit hints,"
    " not semantic proof.",
    "Recognized symbols and registrations do not establish full-module source portability.",
)


def _mask_comments(text: str) -> str:
    """Replace comments by spaces while preserving strings and every newline."""
    result = list(text)
    index = 0
    state = "normal"
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "normal" and current == "/" and following == "/":
            result[index] = result[index + 1] = " "
            index += 2
            while index < len(text) and text[index] != "\n":
                result[index] = " "
                index += 1
            continue
        if state == "normal" and current == "/" and following == "*":
            result[index] = result[index + 1] = " "
            index += 2
            while index < len(text):
                if text[index] == "*" and index + 1 < len(text) and text[index + 1] == "/":
                    result[index] = result[index + 1] = " "
                    index += 2
                    break
                if text[index] != "\n":
                    result[index] = " "
                index += 1
            continue
        if state == "normal" and current in ('"', "'"):
            state = current
        elif state != "normal" and current == "\\":
            index += 2
            continue
        elif state != "normal" and current == state:
            state = "normal"
        index += 1
    return "".join(result)


def _mask_literals(text: str) -> str:
    """Replace C string and character literal contents while preserving locations."""
    result = list(text)
    index = 0
    delimiter: str | None = None
    while index < len(text):
        current = text[index]
        if delimiter is None and current in ('"', "'"):
            delimiter = current
            result[index] = " "
        elif delimiter is not None:
            if current != "\n":
                result[index] = " "
            if current == "\\" and index + 1 < len(text):
                index += 1
                if text[index] != "\n":
                    result[index] = " "
            elif current == delimiter:
                delimiter = None
        index += 1
    return "".join(result)


def _line_offsets(text: str) -> list[int]:
    return [0, *(match.end() for match in re.finditer("\n", text))]


def _location(offset: int, offsets: list[int], source_path: str | None) -> SourceLocation:
    line_index = bisect_right(offsets, offset) - 1
    return SourceLocation(source_path, line_index + 1, offset - offsets[line_index] + 1)


def _span(
    start: int,
    end: int,
    offsets: list[int],
    source_path: str | None,
) -> SourceSpan:
    return SourceSpan(_location(start, offsets, source_path), _location(end, offsets, source_path))


def _next_nonspace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _closing_parenthesis(text: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _is_gwyddion_symbol(symbol: str, profile: GwyddionCompatibilityProfile) -> bool:
    return symbol.startswith(profile.gwyddion_symbol_prefixes)


def _is_gtk_symbol(symbol: str, profile: GwyddionCompatibilityProfile) -> bool:
    return symbol.startswith(profile.gtk_symbol_prefixes)


def _is_glib_symbol(symbol: str, profile: GwyddionCompatibilityProfile) -> bool:
    return symbol.startswith(profile.glib_symbol_prefixes) or symbol in {
        "gboolean",
        "gchar",
        "gdouble",
        "gint",
        "gpointer",
        "guint",
        "gulong",
    }


def _classification(symbol: str, profile: GwyddionCompatibilityProfile) -> SymbolClassification:
    if symbol in profile.registration_calls or symbol.startswith("GWY_MODULE_QUERY"):
        return SymbolClassification.MODULE_REGISTRATION
    if _is_gtk_symbol(symbol, profile):
        return SymbolClassification.GUI_GTK
    if _is_glib_symbol(symbol, profile):
        return SymbolClassification.GLIB_RUNTIME
    if symbol.startswith(_PROCESS_NUMERICAL_PREFIXES):
        return SymbolClassification.PROCESS_NUMERICAL
    if symbol.startswith(("gwy_data_field_", "gwy_data_line_", "gwy_brick_", "gwy_surface_")):
        return SymbolClassification.DATA_MODEL
    if symbol.startswith(("gwy_selection_", "gwy_layer_", "gwy_vector_layer_", "gwy_plain_tool_")):
        return SymbolClassification.SELECTION_LAYER
    if symbol.startswith(("gwy_params_", "gwy_param_", "gwy_app_settings_")):
        return SymbolClassification.PARAMETERS_SETTINGS
    if symbol.startswith(("gwy_app_undo_", "gwy_app_channel_log_", "gwy_container_set_")):
        return SymbolClassification.PUBLICATION_LOGGING
    if symbol.startswith(("gwy_container_", "gwy_app_")):
        return SymbolClassification.CONTAINER_APPLICATION
    return SymbolClassification.UNKNOWN


def _support_status(
    symbol: str,
    classification: SymbolClassification,
    profile: GwyddionCompatibilityProfile,
) -> SymbolSupportStatus:
    if symbol in profile.mapping_dict:
        return SymbolSupportStatus.MAPPED
    if classification is SymbolClassification.GUI_GTK:
        return SymbolSupportStatus.UNSUPPORTED
    if classification is SymbolClassification.UNKNOWN:
        return SymbolSupportStatus.UNKNOWN
    return SymbolSupportStatus.ADAPTER_REQUIRED


def _registration_kind(symbol: str) -> RegistrationKind | None:
    if symbol in _KNOWN_REGISTRATION_KINDS:
        return _KNOWN_REGISTRATION_KINDS[symbol]
    if symbol.startswith("GWY_MODULE_QUERY") or symbol.endswith("_func_register"):
        return RegistrationKind.UNKNOWN
    return None


def _registration_name(symbol: str, raw_call: str) -> str | None:
    if symbol.startswith("GWY_MODULE_QUERY"):
        match = re.search(r",\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)$", raw_call, re.DOTALL)
        return match.group(1) if match else None
    if symbol in {"gwy_process_func_register", "gwy_file_func_register"}:
        match = re.search(r'\(\s*"((?:[^"\\]|\\.)*)"', raw_call, re.DOTALL)
        return match.group(1) if match else None
    return None


def _deduplicated(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(OrderedDict.fromkeys(values))


def audit_gwyddion_source(
    source_text: str,
    *,
    source_path: str | None = None,
    profile: GwyddionCompatibilityProfile | None = None,
) -> GwyddionModuleAuditReport:
    """Audit C source text lexically without executing, compiling, or writing files."""
    if not isinstance(source_text, str):
        raise InvalidGwyddionSourceError("source_text must be a str")
    if source_path is not None and not isinstance(source_path, str):
        raise TypeError("source_path must be a str or None")
    if profile is None:
        profile = gwyddion_2_71_profile()
    if not isinstance(profile, GwyddionCompatibilityProfile):
        raise TypeError("profile must be a GwyddionCompatibilityProfile")

    comment_masked = _mask_comments(source_text)
    lexical_text = _mask_literals(comment_masked)
    offsets = _line_offsets(source_text)
    includes = tuple(
        IncludeReference(
            name=match.group(2),
            is_local=match.group(1) == '"',
            span=_span(match.start(2), match.end(2), offsets, source_path),
        )
        for match in _INCLUDE.finditer(comment_masked)
    )
    symbol_occurrences: OrderedDict[str, list[SourceSpan]] = OrderedDict()
    call_occurrences: OrderedDict[str, list[SourceSpan]] = OrderedDict()
    dependency_occurrences: OrderedDict[str, list[SourceSpan]] = OrderedDict()
    registrations: list[ModuleRegistration] = []

    for match in _IDENTIFIER.finditer(lexical_text):
        symbol = match.group(0)
        symbol_span = _span(match.start(), match.end(), offsets, source_path)
        following = _next_nonspace(lexical_text, match.end())
        is_call = following < len(lexical_text) and lexical_text[following] == "("
        if _is_gwyddion_symbol(symbol, profile):
            symbol_occurrences.setdefault(symbol, []).append(symbol_span)
            if is_call:
                call_occurrences.setdefault(symbol, []).append(symbol_span)
                kind = _registration_kind(symbol)
                if kind is not None:
                    closing = _closing_parenthesis(lexical_text, following)
                    call_end = closing + 1 if closing is not None else match.end()
                    raw_call = source_text[match.start() : call_end]
                    registrations.append(
                        ModuleRegistration(
                            kind=kind,
                            callee=symbol,
                            declared_name=_registration_name(symbol, raw_call),
                            span=_span(match.start(), call_end, offsets, source_path),
                        )
                    )
        elif _is_gtk_symbol(symbol, profile) or _is_glib_symbol(symbol, profile):
            dependency_occurrences.setdefault(symbol, []).append(symbol_span)

    symbols = tuple(
        SymbolReference(
            symbol=symbol,
            classification=_classification(symbol, profile),
            support_status=_support_status(symbol, _classification(symbol, profile), profile),
            occurrences=tuple(occurrences),
            call_occurrences=tuple(call_occurrences.get(symbol, [])),
        )
        for symbol, occurrences in symbol_occurrences.items()
    )
    dependencies = tuple(
        DependencyReference(
            name=name,
            classification=_classification(name, profile),
            support_status=_support_status(name, _classification(name, profile), profile),
            occurrences=tuple(occurrences),
        )
        for name, occurrences in dependency_occurrences.items()
    )
    classifications = {symbol.symbol: symbol.classification for symbol in symbols}
    selection = _deduplicated(
        symbol.symbol
        for symbol in symbols
        if classifications[symbol.symbol] is SymbolClassification.SELECTION_LAYER
    )
    parameters = _deduplicated(
        symbol.symbol
        for symbol in symbols
        if classifications[symbol.symbol] is SymbolClassification.PARAMETERS_SETTINGS
    )
    publication = _deduplicated(
        symbol.symbol
        for symbol in symbols
        if classifications[symbol.symbol] is SymbolClassification.PUBLICATION_LOGGING
    )
    mutation_hints = _deduplicated(
        f"possible data-field mutation: {symbol.symbol}"
        for symbol in symbols
        if symbol.symbol.startswith("gwy_data_field_")
        and any(marker in symbol.symbol for marker in _MUTATING_DATA_FIELD_MARKERS)
    )
    blockers: list[str] = []
    if any(
        dependency.classification is SymbolClassification.GUI_GTK
        for dependency in dependencies
    ):
        blockers.append("GUI/GTK dependency requires an explicit adapter and remains unsupported.")
    if selection:
        blockers.append("Selection/layer dependency requires an explicit adapter.")
    if parameters:
        blockers.append("Parameter/settings dependency requires an explicit adapter.")
    if publication:
        blockers.append("Publication/logging dependency requires an explicit adapter.")
    blockers.extend(
        f"Unknown support status: {symbol.symbol}"
        for symbol in symbols
        if symbol.support_status is SymbolSupportStatus.UNKNOWN
    )
    warnings = _deduplicated(
        [
            "Static source inventory does not establish semantic equivalence.",
            "No binary compatibility, dynamic module loading, or automatic translation"
            " is provided.",
            "License compatibility must be reviewed per migrated module.",
        ]
    )
    totals = dict.fromkeys(SymbolSupportStatus, 0)
    for symbol_reference in symbols:
        totals[symbol_reference.support_status] += 1
    for dependency_reference in dependencies:
        totals[dependency_reference.support_status] += 1
    digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    evidence = AuditEvidence(
        source_sha256=digest,
        scanner="spmkit.compat.gwyddion.lexical-source-audit",
        scanner_version=1,
        limitations=_LIMITATIONS,
    )
    return GwyddionModuleAuditReport(
        schema_version=REPORT_SCHEMA_VERSION,
        module_path=source_path,
        content_sha256=digest,
        profile=profile,
        evidence=evidence,
        registrations=tuple(registrations),
        includes=includes,
        gwyddion_symbols=symbols,
        gtk_glib_dependencies=dependencies,
        mapped_total=totals[SymbolSupportStatus.MAPPED],
        adapter_required_total=totals[SymbolSupportStatus.ADAPTER_REQUIRED],
        unsupported_total=totals[SymbolSupportStatus.UNSUPPORTED],
        unknown_total=totals[SymbolSupportStatus.UNKNOWN],
        has_ui_dependency=any(
            dependency.classification is SymbolClassification.GUI_GTK for dependency in dependencies
        ),
        likely_selection_dependencies=selection,
        likely_parameter_system_dependencies=parameters,
        likely_publication_logging_dependencies=publication,
        conservative_mutation_hints=mutation_hints,
        migration_blockers=tuple(blockers),
        migration_warnings=warnings,
        evidence_limitations=_LIMITATIONS,
    )
