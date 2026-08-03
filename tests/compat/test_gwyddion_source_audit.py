"""Source-fact tests for the lexical Gwyddion migration auditor."""

from __future__ import annotations

from spmkit.compat.gwyddion.source_audit import audit_gwyddion_source
from spmkit.compat.gwyddion.symbols import (
    RegistrationKind,
    SymbolClassification,
    SymbolSupportStatus,
)

_SOURCE_SNIPPETS = {
    "modules/tools/pathlevel.c": "\n" * 110
    + '    gwy_tool_func_register("pathlevel", callback);\n'
    + "GWY_MODULE_QUERY2(module_info, pathlevel)\n"
    + "#include <gtk/gtk.h>\n"
    + "gtk_widget_show(widget);\n"
    + "gwy_plain_tool_connect_selection(tool);\n"
    + "gwy_params_new_from_settings();\n",
    "modules/tools/filter.c": (
        'gwy_tool_func_register("filter", callback);\n'
        "gwy_data_field_area_filter_min_max(field);\n"
    ),
    "modules/process/median-bg.c": (
        'gwy_process_func_register("median-bg", callback);\n' "gwy_app_channel_log_add_proc();\n"
    ),
}


def _audit(relative: str):
    return audit_gwyddion_source(
        _SOURCE_SNIPPETS[relative],
        source_path=relative,
    )


def test_lexical_scanner_ignores_comments_and_literals_and_retains_calls() -> None:
    source = """
#include "local-header.h"
/* gwy_process_func_register("fake", nope); GWY_MODULE_QUERY2(fake, wrong) */
const char *message = "gwy_tool_func_register(GWY_FAKE)";
const char quoted = 'g';
GWY_MODULE_QUERY2(module_info, synthetic)
gwy_process_func_register(
    "real-process",
    callback,
    0
);
gwy_data_field_get_xres(field);
gwy_data_field_get_xres(field);
gwy_future_symbol();
gwy_custom_func_register();
gtk_widget_show(widget);
gwyish_data_field_get_xres(field);
"""
    report = audit_gwyddion_source(source, source_path="synthetic.c")
    assert [(item.kind, item.declared_name) for item in report.registrations] == [
        (RegistrationKind.UNKNOWN, "synthetic"),
        (RegistrationKind.PROCESS, "real-process"),
        (RegistrationKind.UNKNOWN, None),
    ]
    symbols = {item.symbol: item for item in report.gwyddion_symbols}
    assert "gwy_tool_func_register" not in symbols
    assert "gwyish_data_field_get_xres" not in symbols
    assert len(symbols["gwy_data_field_get_xres"].occurrences) == 2
    assert len(symbols["gwy_data_field_get_xres"].call_occurrences) == 2
    assert symbols["gwy_data_field_get_xres"].support_status is SymbolSupportStatus.MAPPED
    assert symbols["gwy_future_symbol"].classification is SymbolClassification.UNKNOWN
    assert symbols["gwy_future_symbol"].support_status is SymbolSupportStatus.UNKNOWN
    assert report.includes[0].name == "local-header.h"
    assert report.includes[0].is_local is True
    assert report.has_ui_dependency is True
    assert report.unsupported_total == 1


def test_incomplete_source_never_crashes_the_lexical_inventory() -> None:
    report = audit_gwyddion_source("gwy_data_field_get_xres(field; /* unfinished")
    assert report.gwyddion_symbols[0].symbol == "gwy_data_field_get_xres"
    assert len(report.gwyddion_symbols[0].call_occurrences) == 1


def test_representative_path_level_source_facts_are_extracted_with_locations() -> None:
    report = _audit("modules/tools/pathlevel.c")
    assert report.module_path == "modules/tools/pathlevel.c"
    assert any(item.kind is RegistrationKind.TOOL for item in report.registrations)
    assert any(item.declared_name == "pathlevel" for item in report.registrations)
    assert any(include.name == "gtk/gtk.h" for include in report.includes)
    assert report.has_ui_dependency is True
    assert "gwy_plain_tool_connect_selection" in report.likely_selection_dependencies
    assert "gwy_params_new_from_settings" in report.likely_parameter_system_dependencies
    tool_registration = next(
        item for item in report.registrations if item.kind is RegistrationKind.TOOL
    )
    assert tool_registration.span.start.line == 111
    assert tool_registration.span.start.column == 5


def test_representative_filter_and_median_sources_remain_audit_inventory_only() -> None:
    filter_report = _audit("modules/tools/filter.c")
    median_report = _audit("modules/process/median-bg.c")
    assert any(item.kind is RegistrationKind.TOOL for item in filter_report.registrations)
    filter_symbols = {item.symbol: item for item in filter_report.gwyddion_symbols}
    assert filter_symbols["gwy_data_field_area_filter_min_max"].classification is (
        SymbolClassification.PROCESS_NUMERICAL
    )
    assert filter_symbols["gwy_data_field_area_filter_min_max"].support_status is (
        SymbolSupportStatus.ADAPTER_REQUIRED
    )
    process_registration = next(
        item for item in median_report.registrations if item.kind is RegistrationKind.PROCESS
    )
    assert process_registration.declared_name == "median-bg"
    assert "gwy_app_channel_log_add_proc" in median_report.likely_publication_logging_dependencies
    assert median_report.migration_warnings
    assert any("does not establish" in warning for warning in median_report.migration_warnings)
