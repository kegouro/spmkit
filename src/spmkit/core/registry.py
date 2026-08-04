"""SPMKit Operation Registry v1.

A minimal, deterministic, metadata-only registry of stable scientific
operations.  It loads the packaged capability ledger
(``spmkit.core.capabilities.json``) exactly once, validates it, and exposes
lookup, filtering and lazy callable resolution.

Scope (v1):
  * metadata and callable resolution only;
  * no generic ``invoke()`` helper (operations have heterogeneous inputs);
  * no Recipe, CLI, workflow, plugin or history system;
  * no Git metadata, timestamps or repository-local paths;
  * no dynamic filesystem scanning;
  * no dependency on docs/ files at runtime.

Callers resolve a callable and invoke it directly with the operation's own
signature.
"""

from __future__ import annotations

import importlib
import importlib.resources
import json
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

__all__ = [
    "CapabilitySpec",
    "ParameterSpec",
    "ReferenceSpec",
    "get_operation",
    "list_operations",
    "filter_operations",
    "resolve_callable",
]

_SCHEMA_VERSION = 1

_REQUIRED_FIELDS = (
    "capability_id", "operation_id", "family", "public_name", "public_import",
    "aliases", "reference", "contract", "parameters", "result_type", "units",
    "mask_semantics", "roi_support", "nan_policy", "border_policy",
    "mutation_policy", "status", "maturity", "evidence", "known_deviations",
)

_MATURITY = frozenset({
    "SPECIFIED", "SOFTWARE_VERIFIED", "NUMERICALLY_VERIFIED",
    "CROSS_VALIDATED", "PHYSICALLY_VALIDATED",
})
_STATUS = frozenset({"stable", "experimental", "deprecated"})
_MASK = frozenset({"none", "include_exclude_ignore", "mask_input", "mask_output"})
_NAN = frozenset({"reject", "propagate", "replace", "not_applicable"})
_BORDER = frozenset({"clipped", "extend", "mirror", "periodic", "not_applicable"})
_MUTATION = frozenset({"none", "returns_new", "in_place"})
_KIND = frozenset({"positional", "keyword_only"})


class RegistryError(ValueError):
    """Raised for invalid registry construction or lookup."""


class UnknownOperationError(KeyError):
    """Raised when an operation_id is not registered."""


class Maturity(Enum):
    SPECIFIED = "SPECIFIED"
    SOFTWARE_VERIFIED = "SOFTWARE_VERIFIED"
    NUMERICALLY_VERIFIED = "NUMERICALLY_VERIFIED"
    CROSS_VALIDATED = "CROSS_VALIDATED"
    PHYSICALLY_VALIDATED = "PHYSICALLY_VALIDATED"


class Status(Enum):
    STABLE = "stable"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


class MutationPolicy(Enum):
    NONE = "none"
    RETURNS_NEW = "returns_new"
    IN_PLACE = "in_place"


class NanPolicy(Enum):
    REJECT = "reject"
    PROPAGATE = "propagate"
    REPLACE = "replace"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ParameterSpec:
    """Explicit scientific parameter metadata."""

    name: str
    kind: str
    required: bool
    has_default: bool
    default: object
    type: str
    enum_values: tuple[str, ...] | None
    bounds: tuple[float, float] | None
    units: str | None
    description: str


@dataclass(frozen=True)
class ReferenceSpec:
    """External reference software identity."""

    software: str
    version: str
    name: str
    profile: str


@dataclass(frozen=True)
class CapabilitySpec:
    """Immutable stable capability record."""

    capability_id: str
    operation_id: str
    family: str
    public_name: str
    public_import: str
    aliases: tuple[str, ...]
    reference: ReferenceSpec
    contract: str
    parameters: tuple[ParameterSpec, ...]
    result_type: str
    units: str
    mask_semantics: str
    roi_support: bool
    nan_policy: NanPolicy
    border_policy: str
    mutation_policy: MutationPolicy
    status: Status
    maturity: Maturity
    evidence: tuple[str, ...]
    known_deviations: tuple[str, ...]


def _load_json() -> Mapping[str, object]:
    resource = importlib.resources.files("spmkit.core").joinpath("capabilities.json")
    with resource.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _validate_public_import(public_import: str) -> None:
    if ":" not in public_import:
        raise RegistryError(f"malformed public import {public_import!r}")
    module, attr = public_import.split(":", 1)
    if not module or not attr:
        raise RegistryError(f"malformed public import {public_import!r}")
    if attr.startswith("_"):
        raise RegistryError(f"private public name {attr!r}")


def _validate_evidence_path(path: str) -> None:
    if path.startswith("/") or ":" in path or "\\" in path:
        raise RegistryError(f"absolute or non-relative evidence path {path!r}")
    if ".reference" in path.split("/"):
        raise RegistryError(f"evidence path under .reference {path!r}")


def _s(raw: Mapping[str, object], key: str) -> str:
    if key not in raw:
        raise RegistryError(f"missing field {key!r}")
    value = raw[key]
    if not isinstance(value, str):
        raise RegistryError(f"{key} must be a string, got {type(value).__name__}")
    return value


def _s_or_none(raw: Mapping[str, object], key: str) -> str | None:
    if key not in raw:
        raise RegistryError(f"missing field {key!r}")
    value = raw[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise RegistryError(f"{key} must be a string or null, "
                            f"got {type(value).__name__}")
    return value


def _strs(raw: Mapping[str, object], key: str) -> tuple[str, ...]:
    if key not in raw:
        raise RegistryError(f"missing field {key!r}")
    value = raw[key]
    if not isinstance(value, list):
        raise RegistryError(f"{key} must be a list, got {type(value).__name__}")
    for item in value:
        if not isinstance(item, str):
            raise RegistryError(
                f"{key} items must be strings, got {type(item).__name__}")
    return tuple(value)


def _b(raw: Mapping[str, object], key: str) -> bool:
    if key not in raw:
        raise RegistryError(f"missing field {key!r}")
    value = raw[key]
    if not isinstance(value, bool):
        raise RegistryError(f"{key} must be a Boolean, got {type(value).__name__}")
    return value


def _parse_parameter(raw: Mapping[str, object]) -> ParameterSpec:
    _reject_unknown_fields(raw, _KNOWN_PARAMETER_FIELDS, "parameter record")
    name = _s(raw, "name")
    kind = _s(raw, "kind")
    if kind not in _KIND:
        raise RegistryError(f"parameter {name}: unknown kind {kind!r}")
    required = _b(raw, "required")
    has_default = _b(raw, "has_default")
    if "default" not in raw:
        raise RegistryError(f"parameter {name}: missing default field")
    default = raw["default"]
    if not has_default and default is not None:
        raise RegistryError(f"parameter {name}: default without has_default")
    enum_values_raw = raw.get("enum_values")
    enum_values: tuple[str, ...] | None = None
    if enum_values_raw is not None:
        if not isinstance(enum_values_raw, list):
            raise RegistryError("enum_values must be a list or null")
        for item in enum_values_raw:
            if not isinstance(item, str):
                raise RegistryError(
                    f"enum_values items must be strings, got {type(item).__name__}")
        enum_values = tuple(enum_values_raw)
    bounds_raw = raw.get("bounds")
    bounds: tuple[float, float] | None = None
    if bounds_raw is not None:
        if not isinstance(bounds_raw, list) or len(bounds_raw) != 2:
            raise RegistryError(f"parameter {name}: bounds must be a 2-list or null")
        items = []
        for item in bounds_raw:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise RegistryError(
                    f"parameter {name}: bounds items must be real numbers")
            value = float(item)
            if not math.isfinite(value):
                raise RegistryError(
                    f"parameter {name}: bounds items must be finite")
            items.append(value)
        if items[0] > items[1]:
            raise RegistryError(
                f"parameter {name}: bounds must be ordered low..high")
        bounds = (items[0], items[1])
    return ParameterSpec(
        name=name,
        kind=kind,
        required=required,
        has_default=has_default,
        default=default,
        type=_s(raw, "type"),
        enum_values=enum_values,
        bounds=bounds,
        units=_s_or_none(raw, "units"),
        description=_s(raw, "description"),
    )


def _parse_capability(raw: Mapping[str, object]) -> CapabilitySpec:
    _reject_unknown_fields(raw, _KNOWN_CAPABILITY_FIELDS, "capability record")
    for field_name in _REQUIRED_FIELDS:
        if field_name not in raw:
            raise RegistryError(f"missing required field {field_name!r}")
    capability_id = _s(raw, "capability_id")
    operation_id = _s(raw, "operation_id")
    public_import = _s(raw, "public_import")
    _validate_public_import(public_import)
    for path in _strs(raw, "evidence"):
        _validate_evidence_path(path)
    maturity = _s(raw, "maturity")
    if maturity not in _MATURITY:
        raise RegistryError(f"{capability_id}: unknown maturity {maturity!r}")
    status = _s(raw, "status")
    if status not in _STATUS:
        raise RegistryError(f"{capability_id}: unknown status {status!r}")
    mask = _s(raw, "mask_semantics")
    if mask not in _MASK:
        raise RegistryError(f"{capability_id}: unknown mask_semantics {mask!r}")
    nan = _s(raw, "nan_policy")
    if nan not in _NAN:
        raise RegistryError(f"{capability_id}: unknown nan_policy {nan!r}")
    border = _s(raw, "border_policy")
    if border not in _BORDER:
        raise RegistryError(f"{capability_id}: unknown border_policy {border!r}")
    mutation = _s(raw, "mutation_policy")
    if mutation not in _MUTATION:
        raise RegistryError(f"{capability_id}: unknown mutation_policy {mutation!r}")
    if "reference" not in raw:
        raise RegistryError(f"{capability_id}: missing reference field")
    ref_raw = raw["reference"]
    if not isinstance(ref_raw, dict):
        raise RegistryError(f"{capability_id}: reference must be an object")
    ref_map = cast(Mapping[str, object], ref_raw)
    _reject_unknown_fields(ref_map, {"software", "version", "name", "profile"},
                           f"{capability_id}: reference")
    reference = ReferenceSpec(
        software=_s(ref_map, "software"),
        version=_s(ref_map, "version"),
        name=_s(ref_map, "name"),
        profile=_s(ref_map, "profile"),
    )
    parameters = tuple(_parse_parameter(cast(Mapping[str, object], p))
                       for p in cast(Iterable[object], raw["parameters"]))
    return CapabilitySpec(
        capability_id=capability_id,
        operation_id=operation_id,
        family=_s(raw, "family"),
        public_name=_s(raw, "public_name"),
        public_import=public_import,
        aliases=_strs(raw, "aliases"),
        reference=reference,
        contract=_s(raw, "contract"),
        parameters=parameters,
        result_type=_s(raw, "result_type"),
        units=_s(raw, "units"),
        mask_semantics=mask,
        roi_support=_b(raw, "roi_support"),
        nan_policy=NanPolicy(nan),
        border_policy=border,
        mutation_policy=MutationPolicy(mutation),
        status=Status(status),
        maturity=Maturity(maturity),
        evidence=_strs(raw, "evidence"),
        known_deviations=_strs(raw, "known_deviations"),
    )


_KNOWN_TOP_LEVEL = {"schema_version", "capabilities"}
_KNOWN_CAPABILITY_FIELDS = set(_REQUIRED_FIELDS)
_KNOWN_PARAMETER_FIELDS = {
    "name", "kind", "required", "has_default", "default", "type",
    "enum_values", "bounds", "units", "description",
}


def _reject_unknown_fields(raw: Mapping[str, object], known: set[str],
                           context: str) -> None:
    for key in raw:
        if key not in known:
            raise RegistryError(f"{context}: unknown field {key!r}")


def _build_registry() -> tuple[CapabilitySpec, ...]:
    data = _load_json()
    if not isinstance(data, dict):
        raise RegistryError("ledger root must be an object")
    _reject_unknown_fields(data, _KNOWN_TOP_LEVEL, "ledger")
    version = data.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) \
            or version != _SCHEMA_VERSION:
        raise RegistryError(
            f"unsupported schema version {version!r}")
    raw_caps = data.get("capabilities")
    if not isinstance(raw_caps, list):
        raise RegistryError("capabilities must be a list")
    specs = [_parse_capability(c) for c in raw_caps]
    # deterministic ordering by capability_id
    specs.sort(key=lambda s: s.capability_id)
    seen_cap: set[str] = set()
    seen_op: set[str] = set()
    seen_import: set[str] = set()
    for spec in specs:
        if spec.capability_id in seen_cap:
            raise RegistryError(f"duplicate capability ID {spec.capability_id}")
        if spec.operation_id in seen_op:
            raise RegistryError(f"duplicate operation ID {spec.operation_id}")
        if spec.public_import in seen_import:
            raise RegistryError(f"duplicate public import {spec.public_import}")
        seen_cap.add(spec.capability_id)
        seen_op.add(spec.operation_id)
        seen_import.add(spec.public_import)
    return tuple(specs)


_REGISTRY: tuple[CapabilitySpec, ...] | None = None


def _registry() -> tuple[CapabilitySpec, ...]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_operation(operation_id: str) -> CapabilitySpec:
    """Return the capability record for an operation ID."""
    for spec in _registry():
        if spec.operation_id == operation_id:
            return spec
    raise UnknownOperationError(operation_id)


def list_operations() -> tuple[CapabilitySpec, ...]:
    """Return all registered operations in deterministic order."""
    return _registry()


def filter_operations(
    family: str | None = None,
    maturity: str | Maturity | None = None,
) -> tuple[CapabilitySpec, ...]:
    """Return operations filtered by family and/or maturity."""
    want_maturity: Maturity | None = None
    if maturity is not None:
        if isinstance(maturity, Maturity):
            want_maturity = maturity
        else:
            if maturity not in _MATURITY:
                raise RegistryError(f"unknown maturity {maturity!r}")
            want_maturity = Maturity(maturity)
    out = []
    for spec in _registry():
        if family is not None and spec.family != family:
            continue
        if want_maturity is not None and spec.maturity != want_maturity:
            continue
        out.append(spec)
    return tuple(out)


def resolve_callable(operation_id: str) -> Callable[..., object]:
    """Resolve the public callable for an operation ID (lazy import)."""
    spec = get_operation(operation_id)
    module_name, attr = spec.public_import.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if fn is None:
        raise RegistryError(
            f"public import {spec.public_import!r} does not resolve")
    if not callable(fn):
        raise RegistryError(
            f"public import {spec.public_import!r} is not callable")
    if attr.startswith("_"):
        raise RegistryError(f"private callable {attr!r}")
    return fn
