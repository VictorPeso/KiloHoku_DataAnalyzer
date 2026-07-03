"""
Entidades del dominio.
"""

from etl.domain.entities.irsa_light_curve_source import (
    IrsaLightCurveSource,
)
from etl.domain.entities.light_curve import LightCurve
from etl.domain.entities.light_curve_observation import (
    LightCurveObservation,
)
from etl.domain.entities.star_candidate import StarCandidate

__all__ = [
    "IrsaLightCurveSource",
    "LightCurve",
    "LightCurveObservation",
    "StarCandidate",
]