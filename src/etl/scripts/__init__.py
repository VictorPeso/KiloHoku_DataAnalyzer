"""
Scripts ejecutables del proyecto ETL.
"""

from etl.scripts.import_candidates_from_csv import (
    import_candidates_from_csv,
)

__all__ = ["import_candidates_from_csv"]