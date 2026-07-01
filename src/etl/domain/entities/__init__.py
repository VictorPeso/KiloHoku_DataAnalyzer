"""
Entidades principales del dominio.
"""

from etl.domain.entities.light_curve import LightCurve
from etl.domain.entities.light_curve_observation import (
    LightCurveObservation,
)
from etl.domain.entities.star_candidate import StarCandidate

__all__ = [
    "LightCurve",
    "LightCurveObservation",
    "StarCandidate",
]