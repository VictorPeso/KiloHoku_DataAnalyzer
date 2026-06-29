"""
Pipelines disponibles en el proceso ETL.
"""

from etl.pipelines.import_star_candidates_pipeline import (
    ImportStarCandidatesPipeline,
    ImportStarCandidatesResult,
)

__all__ = [
    "ImportStarCandidatesPipeline",
    "ImportStarCandidatesResult",
]