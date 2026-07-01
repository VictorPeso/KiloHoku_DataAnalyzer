"""
Repositorios de acceso a los datos persistidos.
"""

from etl.database.repositories.light_curve_repository import (
    LightCurveRepository,
    SaveLightCurvesResult,
    StarCandidateNotFoundError,
)
from etl.database.repositories.star_candidate_repository import (
    SaveManyResult,
    StarCandidateRepository,
)

__all__ = [
    "LightCurveRepository",
    "SaveLightCurvesResult",
    "StarCandidateNotFoundError",
    "SaveManyResult",
    "StarCandidateRepository",
]