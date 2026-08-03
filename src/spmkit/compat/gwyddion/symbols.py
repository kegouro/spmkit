"""Immutable source-location and symbol-inventory models for static auditing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RegistrationKind(StrEnum):
    """Gwyddion module registration families recognized by the source auditor."""

    PROCESS = "process"
    TOOL = "tool"
    FILE = "file"
    GRAPH = "graph"
    LAYER = "layer"
    VOLUME = "volume"
    XYZ = "xyz"
    CURVE_MAP = "curve-map"
    UNKNOWN = "unknown"


class SymbolClassification(StrEnum):
    """Conservative ownership-oriented symbol classes, not semantic proof."""

    DATA_MODEL = "data/model"
    PROCESS_NUMERICAL = "process/numerical"
    CONTAINER_APPLICATION = "container/application"
    SELECTION_LAYER = "selection/layer"
    PARAMETERS_SETTINGS = "parameters/settings"
    PUBLICATION_LOGGING = "publication/logging"
    GUI_GTK = "GUI/GTK"
    GLIB_RUNTIME = "GLib/runtime"
    MODULE_REGISTRATION = "module/registration"
    UNKNOWN = "unknown"


class SymbolSupportStatus(StrEnum):
    """Current migration support state; unproven names stay unknown."""

    MAPPED = "mapped"
    ADAPTER_REQUIRED = "adapter-required"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceLocation:
    """One-based source position controlled entirely by the audit caller."""

    source_path: str | None
    line: int
    column: int

    def __post_init__(self) -> None:
        if self.line < 1 or self.column < 1:
            raise ValueError("source locations are one-based")


@dataclass(frozen=True)
class SourceSpan:
    """Half-open source range represented by stable start and end locations."""

    start: SourceLocation
    end: SourceLocation


@dataclass(frozen=True)
class IncludeReference:
    """One literal preprocessor include, retained without preprocessing it."""

    name: str
    is_local: bool
    span: SourceSpan


@dataclass(frozen=True)
class ModuleRegistration:
    """A registration-looking function or macro call detected lexically."""

    kind: RegistrationKind
    callee: str
    declared_name: str | None
    span: SourceSpan


@dataclass(frozen=True)
class SymbolReference:
    """A deduplicated symbol with every lexical occurrence retained in order."""

    symbol: str
    classification: SymbolClassification
    support_status: SymbolSupportStatus
    occurrences: tuple[SourceSpan, ...]
    call_occurrences: tuple[SourceSpan, ...]


@dataclass(frozen=True)
class DependencyReference:
    """A GTK/GLib dependency inventory entry with ordered occurrences."""

    name: str
    classification: SymbolClassification
    support_status: SymbolSupportStatus
    occurrences: tuple[SourceSpan, ...]
