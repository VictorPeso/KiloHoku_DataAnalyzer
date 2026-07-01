"""
Modelos ORM registrados por SQLAlchemy.
"""

from etl.database.models.light_curve_model import LightCurveModel
from etl.database.models.light_curve_observation_model import (
    LightCurveObservationModel,
)
from etl.database.models.star_candidate_model import (
    StarCandidateModel,
)

__all__ = [
    "LightCurveModel",
    "LightCurveObservationModel",
    "StarCandidateModel",
]