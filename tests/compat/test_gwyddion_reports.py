"""Deterministic serialization tests for static Gwyddion audit reports."""

from __future__ import annotations

import json

import pytest

from spmkit.compat.gwyddion.errors import InvalidGwyddionSourceError
from spmkit.compat.gwyddion.reports import canonical_report_json, report_from_dict, report_to_dict
from spmkit.compat.gwyddion.source_audit import audit_gwyddion_source


def _report():
    return audit_gwyddion_source(
        """
#include <gtk/gtk.h>
GWY_MODULE_QUERY2(module_info, report_sample)
gwy_process_func_register("report-sample", callback);
gwy_data_field_get_yreal(field);
""",
        source_path="modules/process/report-sample.c",
    )


def test_canonical_json_is_stable_and_round_trips() -> None:
    first = _report()
    second = _report()
    first_json = canonical_report_json(first)
    assert first_json == canonical_report_json(second)
    reconstructed = report_from_dict(json.loads(first_json))
    assert report_to_dict(reconstructed) == report_to_dict(first)
    assert canonical_report_json(reconstructed) == first_json
    assert "modules/process/report-sample.c" in first_json


def test_audit_rejects_non_text_source_without_writing() -> None:
    with pytest.raises(InvalidGwyddionSourceError):
        audit_gwyddion_source(b"gwy_process_func_register")  # type: ignore[arg-type]
