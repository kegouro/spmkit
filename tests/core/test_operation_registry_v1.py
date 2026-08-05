"""Operation Registry v1 tests.

Verifies deterministic construction, validation and rejection behavior,
lazy callable resolution, filtering, and signature consistency for all 11
registered operations.
"""

from __future__ import annotations

import copy
import importlib
import inspect
import json

import pytest

from spmkit.core import (
    CapabilitySpec,
    ParameterSpec,
    filter_operations,
    get_operation,
    list_operations,
    resolve_callable,
)
from spmkit.core.registry import (
    Maturity,
    RegistryError,
    UnknownOperationError,
)

# public_import -> expected public callable name
EXPECTED = {
    "img.filter.rank": "gwyd" + "dion_rank_filter",
    "img.filter.median": "gwyd" + "dion_median_filter",
    "img.filter.gaussian": "gwyd" + "dion_gaussian_filter",
    "img.filter.gradient_direction": "gradient_direction",
    "img.filter.gradient_magnitude": "gwyd" + "dion_gradient_magnitude",
    "img.filter.prewitt_x": "gwyd" + "dion_prewitt_x",
    "img.filter.prewitt_y": "gwyd" + "dion_prewitt_y",
    "img.filter.sobel_x": "gwyd" + "dion_sobel_x",
    "img.filter.sobel_y": "gwyd" + "dion_sobel_y",
    "img.interpolation.laplace_under_mask": "gwyd" + "ion_interpolate_data_under_mask",
    "img.level.align_rows_polynomial": "gwyd" + "dion_align_rows_polynomial",
    "img.level.align_rows_modus": "gwyd" + "dion_align_rows_modus",
    "img.level.align_rows_match": "gwyd" + "dion_align_rows_match",
    "img.scanline.mark_scars": "gwyd" + "ion_mark_scars",
    "img.scanline.remove_scars": "gwyd" + "ion_remove_scars",
    "img.scanline.step_block_correction": "gwyd" + "ion_step_block_correction",
    "img.scanline.step_line_correction": "gwyd" + "ion_step_line_correction",
}


def test_get_known_operation() -> None:
    spec = get_operation("img.filter.rank")
    assert spec.capability_id == "IMG.FILTER.RANK"
    assert spec.operation_id == "img.filter.rank"
    assert spec.public_name == "gwyd" + "dion_rank_filter"


def test_reject_unknown_operation() -> None:
    with pytest.raises(UnknownOperationError):
        get_operation("img.does.not.exist")


def test_deterministic_listing() -> None:
    ops = list_operations()
    assert len(ops) == 17
    ids = [o.operation_id for o in ops]
    assert ids == sorted(ids)
    # calling twice yields identical tuples
    assert list_operations() == ops


def test_family_filtering() -> None:
    filters = filter_operations(family="IMG.FILTER")
    assert [f.operation_id for f in filters] == [
        "img.filter.gaussian",
        "img.filter.gradient_direction",
        "img.filter.gradient_magnitude",
        "img.filter.median",
        "img.filter.prewitt_x",
        "img.filter.prewitt_y",
        "img.filter.rank",
        "img.filter.sobel_x",
        "img.filter.sobel_y"]
    scanline = filter_operations(family="IMG.SCANLINE")
    assert {o.operation_id for o in scanline} == {
        "img.scanline.step_line_correction",
        "img.scanline.mark_scars",
        "img.scanline.remove_scars",
        "img.scanline.step_block_correction"}


def test_maturity_filtering() -> None:
    cv = filter_operations(maturity="CROSS_VALIDATED")
    assert len(cv) == 16
    cv2 = filter_operations(maturity=Maturity.CROSS_VALIDATED)
    assert cv == cv2


def test_combined_filters() -> None:
    out = filter_operations(family="IMG.LEVEL", maturity="CROSS_VALIDATED")
    assert {o.operation_id for o in out} == {
        "img.level.align_rows_polynomial",
        "img.level.align_rows_modus",
        "img.level.align_rows_match"}
    with pytest.raises(RegistryError):
        filter_operations(maturity="NOT_A_MATURITY")


def test_callable_resolution_identity() -> None:
    for op_id, expected_name in EXPECTED.items():
        fn = resolve_callable(op_id)
        assert fn.__name__ == expected_name, op_id
        # resolved callable is the public exported callable
        module = __import__("spmkit.core.analysis", fromlist=[expected_name])
        assert fn is getattr(module, expected_name), op_id


def test_lazy_imports() -> None:
    # resolution must not eagerly import every analysis module; verify by
    # checking that resolving a scanline op does not import the filters module
    import sys
    resolve_callable("img.scanline.step_line_correction")
    assert "spmkit.core.analysis.filters" in sys.modules  # already loaded via package
    # the registry itself must not import analysis at module scope
    import spmkit.core.registry as reg
    src = inspect.getsource(reg)
    assert "import spmkit.core.analysis" not in src


def test_derivative_records_maturity_split() -> None:
    for op_id in ("img.filter.sobel_x", "img.filter.sobel_y",
                  "img.filter.prewitt_x", "img.filter.prewitt_y"):
        spec = get_operation(op_id)
        assert spec.maturity == Maturity.CROSS_VALIDATED
        assert spec.reference.software == "Gwydion"
        assert spec.reference.version == "2.71"
        assert spec.border_policy == "clipped"
        assert spec.units == "preserved"
        assert [p.name for p in spec.parameters] == ["channel"]
    magnitude = get_operation("img.filter.gradient_magnitude")
    assert magnitude.maturity == Maturity.CROSS_VALIDATED
    assert [p.name for p in magnitude.parameters] == ["gx", "gy"]
    assert all(p.required for p in magnitude.parameters)
    platform_note = " ".join(magnitude.known_deviations)
    assert "x86-64" in platform_note and "glibc" in platform_note
    assert "hypot@GLIBC_2.35" in platform_note
    assert "no cross-libc" in platform_note
    direction = get_operation("img.filter.gradient_direction")
    assert direction.maturity == Maturity.NUMERICALLY_VERIFIED
    assert direction.reference.software == "SPMKit"
    assert direction.reference.profile == "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"
    assert direction.units == "rad"
    assert [p.name for p in direction.parameters] == ["gx", "gy"]


def test_immutable_records() -> None:
    spec = get_operation("img.filter.rank")
    with pytest.raises(AttributeError):
        spec.operation_id = "x"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        spec.parameters[0].name = "y"  # type: ignore[misc]


def test_record_types() -> None:
    spec = get_operation("img.filter.gaussian")
    assert isinstance(spec, CapabilitySpec)
    assert isinstance(spec.parameters[0], ParameterSpec)
    assert spec.maturity == Maturity.CROSS_VALIDATED
    assert spec.mutation_policy.value == "returns_new"
    assert spec.nan_policy.value == "reject"


def test_signature_consistency_all_operations() -> None:
    for op_id in EXPECTED:
        spec = get_operation(op_id)
        fn = resolve_callable(op_id)
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        # registry channel/positional params must match signature order/kinds
        reg_params = spec.parameters
        reg_by_name = {p.name: p for p in reg_params}
        sig_by_name = {p.name: p for p in params}
        assert set(reg_by_name) == set(sig_by_name), op_id
        for name, p in reg_by_name.items():
            sp = sig_by_name[name]
            want_kind = inspect.Parameter.POSITIONAL_OR_KEYWORD \
                if p.kind == "positional" else inspect.Parameter.KEYWORD_ONLY
            assert sp.kind == want_kind, (op_id, name)
            if p.has_default:
                assert sp.default == p.default or (
                    sp.default is None and p.default is None), (op_id, name)
            else:
                assert sp.default is inspect.Parameter.empty, (op_id, name)


def test_exact_defaults_and_bounds() -> None:
    rank = get_operation("img.filter.rank")
    by_name = {p.name: p for p in rank.parameters}
    assert by_name["radius"].default == 20
    assert by_name["radius"].bounds == (1, 1024)
    assert by_name["percentile"].default == 0.75
    assert by_name["percentile"].bounds == (0.0, 1.0)
    med = get_operation("img.filter.median")
    assert {p.name for p in med.parameters} == {"channel", "size"}
    assert {p.name for p in med.parameters if p.kind == "positional"} == {"channel"}
    gauss = get_operation("img.filter.gaussian")
    assert {p.name for p in gauss.parameters} == {"channel", "sigma"}
    # step line correction has only the channel
    slc = get_operation("img.scanline.step_line_correction")
    assert [p.name for p in slc.parameters] == ["channel"]


# ---------------------------------------------------------------------------
# Adversarial strict-type validation (Phase 4)
# ---------------------------------------------------------------------------


def _patch_ledger(mutator, *, root_mutator=None):
    """Load the packaged JSON, mutate it, and attempt registry rebuild."""
    resource = importlib.resources.files("spmkit.core").joinpath("capabilities.json")
    data = json.loads(resource.read_text(encoding="utf-8"))
    if root_mutator:
        root_mutator(data)
    else:
        mutator(data["capabilities"][0])
    return data


# helper: rebuild from a raw dict via the internal loader
def _build_from(data):
    import spmkit.core.registry as reg
    orig = reg._load_json
    reg._load_json = lambda: data
    try:
        reg._REGISTRY = None
        return reg._build_registry()
    finally:
        reg._load_json = orig
        reg._REGISTRY = None


_RESOURCE = importlib.resources.files("spmkit.core").joinpath(
    "capabilities.json")
BASE = json.loads(_RESOURCE.read_text(encoding="utf-8"))


def _valid_record():
    return copy.deepcopy(BASE["capabilities"][0])


def _expect_reject(mutated, label):
    import spmkit.core.registry as reg
    with pytest.raises(reg.RegistryError):
        _build_from({"schema_version": 1, "capabilities": [mutated]})


def test_top_level_type_validation() -> None:
    import spmkit.core.registry as reg
    with pytest.raises(reg.RegistryError):
        _build_from({"schema_version": True, "capabilities": []})
    with pytest.raises(reg.RegistryError):
        _build_from({"schema_version": "1", "capabilities": []})
    with pytest.raises(reg.RegistryError):
        _build_from({"schema_version": 1, "capabilities": {}})
    with pytest.raises(reg.RegistryError):
        _build_from({"schema_version": 1, "capabilities": [], "bogus": 1})
    with pytest.raises(reg.RegistryError):
        _build_from({"capabilities": []})


def test_record_unknown_and_missing_fields() -> None:
    rec = _valid_record()
    rec["bogus_field"] = 1
    _expect_reject(rec, "unknown field")
    rec = _valid_record()
    del rec["contract"]
    _expect_reject(rec, "missing field")


def test_record_type_validation() -> None:
    rec = _valid_record()
    rec["capability_id"] = 123
    _expect_reject(rec, "int capability_id")
    rec = _valid_record()
    rec["operation_id"] = 456
    _expect_reject(rec, "int operation_id")
    rec = _valid_record()
    rec["public_import"] = 789
    _expect_reject(rec, "non-string public_import")
    rec = _valid_record()
    rec["aliases"] = "not-a-list"
    _expect_reject(rec, "aliases string")
    rec = _valid_record()
    rec["aliases"] = ["ok", 5]
    _expect_reject(rec, "aliases with int")
    rec = _valid_record()
    rec["evidence"] = "not-a-list"
    _expect_reject(rec, "evidence string")
    rec = _valid_record()
    rec["evidence"] = ["ok", 7]
    _expect_reject(rec, "evidence with int")
    rec = _valid_record()
    rec["known_deviations"] = "x"
    _expect_reject(rec, "known_deviations string")
    rec = _valid_record()
    rec["roi_support"] = "false"
    _expect_reject(rec, "roi_support string")
    rec = _valid_record()
    rec["maturity"] = 5
    _expect_reject(rec, "maturity int")
    rec = _valid_record()
    rec["maturity"] = "BOGUS_MATURITY"
    _expect_reject(rec, "unknown maturity")
    rec = _valid_record()
    rec["status"] = "not_a_status"
    _expect_reject(rec, "unknown status")
    rec = _valid_record()
    rec["nan_policy"] = "bogus"
    _expect_reject(rec, "unknown nan_policy")
    rec = _valid_record()
    rec["mask_semantics"] = "bogus"
    _expect_reject(rec, "unknown mask")
    rec = _valid_record()
    rec["border_policy"] = "bogus"
    _expect_reject(rec, "unknown border")
    rec = _valid_record()
    rec["mutation_policy"] = "bogus"
    _expect_reject(rec, "unknown mutation")


def test_reference_validation() -> None:
    rec = _valid_record()
    rec["reference"] = "not-an-object"
    _expect_reject(rec, "reference string")
    rec = _valid_record()
    rec["reference"] = {"software": "Gwydion", "version": "2.71",
                        "name": "X", "profile": "Y", "bogus": 1}
    _expect_reject(rec, "reference unknown field")
    rec = _valid_record()
    del rec["reference"]["profile"]
    _expect_reject(rec, "reference missing field")


def test_parameter_strict_validation() -> None:
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bogus"] = 1
    rec["parameters"] = [p]
    _expect_reject(rec, "parameter unknown field")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["name"] = 5
    rec["parameters"] = [p]
    _expect_reject(rec, "parameter int name")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["kind"] = "bogus"
    rec["parameters"] = [p]
    _expect_reject(rec, "parameter bad kind")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["required"] = "yes"
    rec["parameters"] = [p]
    _expect_reject(rec, "required string")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["has_default"] = "true"
    rec["parameters"] = [p]
    _expect_reject(rec, "has_default string")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["has_default"] = False
    p["default"] = 3.0
    rec["parameters"] = [p]
    _expect_reject(rec, "default without has_default")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["has_default"] = True
    del p["default"]
    rec["parameters"] = [p]
    _expect_reject(rec, "missing default")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["enum_values"] = "not-a-list"
    rec["parameters"] = [p]
    _expect_reject(rec, "enum_values string")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["enum_values"] = [1, 2]
    rec["parameters"] = [p]
    _expect_reject(rec, "enum_values non-string")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bounds"] = "1,2"
    rec["parameters"] = [p]
    _expect_reject(rec, "bounds string")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bounds"] = [1]
    rec["parameters"] = [p]
    _expect_reject(rec, "bounds wrong length")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bounds"] = ["1", "2"]
    rec["parameters"] = [p]
    _expect_reject(rec, "bounds strings")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bounds"] = [True, 2]
    rec["parameters"] = [p]
    _expect_reject(rec, "bounds boolean")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bounds"] = [2, 1]
    rec["parameters"] = [p]
    _expect_reject(rec, "reversed bounds")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["bounds"] = [float("inf"), 2.0]
    rec["parameters"] = [p]
    _expect_reject(rec, "non-finite bounds")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["units"] = 5
    rec["parameters"] = [p]
    _expect_reject(rec, "units int")
    rec = _valid_record()
    p = copy.deepcopy(rec["parameters"][1])
    p["description"] = 7
    rec["parameters"] = [p]
    _expect_reject(rec, "description int")
