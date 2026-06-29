"""
Repositorios de acceso a los datos persistidos.
"""

from etl.database.repositories.star_candidate_repository import (
    SaveManyResult,
    StarCandidateRepository,
)

__all__ = [
    "SaveManyResult",
    "StarCandidateRepository",
]