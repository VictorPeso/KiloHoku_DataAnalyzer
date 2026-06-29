"""
Pipelines disponibles en el proceso ETL.
"""

from etl.pipelines.import_star_candidates_pipeline import (
    CandidateValidationRecord,
    ImportStarCandidatesPipeline,
    ImportStarCandidatesResult,
)

__all__ = [
    "CandidateValidationRecord",
    "ImportStarCandidatesPipeline",
    "ImportStarCandidatesResult",
]