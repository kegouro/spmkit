"""FS-F3 public surface: time-domain viscoelasticity and rate-dependent
AFM mechanics."""

from __future__ import annotations

from spmkit.core.analysis.force_time_protocol import (
    LOADING_RAMP,
    STRESS_RELAXATION,
    CreepResponseResult,
    IndentationRateResult,
    ProtocolRegion,
    RelaxationResponseResult,
    ViscoelasticProtocolResult,
    compute_indentation_rate,
    extract_creep_compliance,
    extract_stress_relaxation,
    identify_viscoelastic_protocol,
    validate_time_axis,
)
from spmkit.core.analysis.force_viscoelastic_errors import (
    ViscoelasticityError,
)
from spmkit.core.analysis.force_viscoelastic_fitting import (
    ViscoelasticFitResult,
    ViscoelasticModelComparisonResult,
    compare_viscoelastic_models,
    fit_generalized_maxwell,
    fit_kelvin_voigt,
    fit_lee_radok_sphere,
    fit_maxwell,
    fit_power_law_relaxation,
    fit_standard_linear_solid,
    fit_ting_sphere,
)
from spmkit.core.analysis.force_viscoelastic_models import (
    forward_generalized_maxwell_modulus,
    forward_generalized_maxwell_normalized,
    forward_kelvin_voigt_compliance,
    forward_maxwell_modulus,
    forward_maxwell_normalized,
    forward_power_law_modulus,
    forward_sls_compliance,
    forward_sls_modulus,
    lee_radok_force,
    reduced_modulus,
    sls_creep_to_relaxation,
    sls_relaxation_to_creep,
    spherical_coefficient,
    ting_force,
)
from spmkit.core.analysis.force_viscoelastic_reliability import (
    ViscoelasticSensitivityResult,
    analyze_viscoelastic_sensitivity,
)
from spmkit.core.analysis.force_volume_viscoelasticity import (
    ForceVolumeViscoelasticityResult,
    fit_force_volume_viscoelasticity,
)

__all__ = [
    "identify_viscoelastic_protocol",
    "compute_indentation_rate",
    "extract_stress_relaxation",
    "extract_creep_compliance",
    "fit_kelvin_voigt",
    "fit_maxwell",
    "fit_standard_linear_solid",
    "fit_generalized_maxwell",
    "fit_power_law_relaxation",
    "fit_lee_radok_sphere",
    "fit_ting_sphere",
    "compare_viscoelastic_models",
    "analyze_viscoelastic_sensitivity",
    "fit_force_volume_viscoelasticity",
    "forward_kelvin_voigt_compliance",
    "forward_maxwell_modulus",
    "forward_maxwell_normalized",
    "forward_sls_modulus",
    "forward_sls_compliance",
    "forward_generalized_maxwell_modulus",
    "forward_generalized_maxwell_normalized",
    "forward_power_law_modulus",
    "lee_radok_force",
    "ting_force",
    "sls_relaxation_to_creep",
    "sls_creep_to_relaxation",
    "reduced_modulus",
    "spherical_coefficient",
    "validate_time_axis",
    "ViscoelasticProtocolResult",
    "ProtocolRegion",
    "IndentationRateResult",
    "RelaxationResponseResult",
    "CreepResponseResult",
    "ViscoelasticFitResult",
    "ViscoelasticModelComparisonResult",
    "ViscoelasticSensitivityResult",
    "ForceVolumeViscoelasticityResult",
    "ViscoelasticityError",
    "LOADING_RAMP",
    "STRESS_RELAXATION",
]
