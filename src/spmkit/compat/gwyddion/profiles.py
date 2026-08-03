"""Version-scoped, conservative Gwyddion source-audit profiles."""

from __future__ import annotations

from dataclasses import dataclass

from spmkit.compat.gwyddion.errors import UnsupportedGwyddionProfileError


@dataclass(frozen=True, order=True)
class GwyddionVersion:
    """A concrete Gwyddion version identity, without compatibility extrapolation."""

    major: int
    minor: int
    patch: int = 0

    def __post_init__(self) -> None:
        if any(value < 0 for value in (self.major, self.minor, self.patch)):
            raise ValueError("Gwyddion version components must be non-negative")

    def __str__(self) -> str:
        if self.patch == 0:
            return f"{self.major}.{self.minor}"
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class GwyddionCompatibilityProfile:
    """Known static-audit facts for one Gwyddion version.

    Recognition does not establish source portability.  Exact mappings are
    deliberately restricted to current SPMKit data-model facts.
    """

    name: str
    version: GwyddionVersion
    registration_calls: tuple[str, ...]
    gwyddion_symbol_prefixes: tuple[str, ...]
    gtk_symbol_prefixes: tuple[str, ...]
    glib_symbol_prefixes: tuple[str, ...]
    exact_symbol_mappings: tuple[tuple[str, str], ...]

    @property
    def mapping_dict(self) -> dict[str, str]:
        """Return a fresh lookup for the profile's explicitly supported mappings."""
        return dict(self.exact_symbol_mappings)


_GWYDDION_2_71_PROFILE = GwyddionCompatibilityProfile(
    name="gwyddion-2.71-source-audit",
    version=GwyddionVersion(2, 71),
    registration_calls=(
        "GWY_MODULE_QUERY",
        "GWY_MODULE_QUERY2",
        "GWY_MODULE_QUERY3",
        "gwy_curve_map_func_register",
        "gwy_file_func_register",
        "gwy_graph_func_register",
        "gwy_layer_func_register",
        "gwy_process_func_register",
        "gwy_tool_func_register",
        "gwy_volume_func_register",
        "gwy_xyz_func_register",
    ),
    gwyddion_symbol_prefixes=("gwy_", "GWY_"),
    gtk_symbol_prefixes=(
        "gtk_",
        "gdk_",
        "pango_",
        "GTK_",
        "GDK_",
        "PANGO_",
        "Gtk",
        "Gdk",
        "Pango",
    ),
    glib_symbol_prefixes=(
        "g_",
        "G_",
        "GLIB_",
        "GIO_",
        "GObject",
        "GType",
        "GQuark",
        "GList",
        "GSList",
    ),
    exact_symbol_mappings=(
        ("gwy_data_field_get_xres", "SPMChannel.shape[1]"),
        ("gwy_data_field_get_yres", "SPMChannel.shape[0]"),
        ("gwy_data_field_get_xreal", "SPMChannel.x_range"),
        ("gwy_data_field_get_yreal", "SPMChannel.y_range"),
    ),
)


def gwyddion_2_71_profile() -> GwyddionCompatibilityProfile:
    """Return the immutable conservative profile for frozen Gwyddion 2.71 source."""
    return _GWYDDION_2_71_PROFILE


def profile_for_version(version: GwyddionVersion) -> GwyddionCompatibilityProfile:
    """Return the explicitly supported profile or fail without approximation."""
    if not isinstance(version, GwyddionVersion):
        raise TypeError("version must be a GwyddionVersion")
    if version == _GWYDDION_2_71_PROFILE.version:
        return _GWYDDION_2_71_PROFILE
    raise UnsupportedGwyddionProfileError(f"no Gwyddion source-audit profile for {version}")
