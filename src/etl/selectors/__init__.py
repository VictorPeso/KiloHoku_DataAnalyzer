"""
Selectores utilizados para elegir elementos entre datos transformados.
"""

from etl.selectors.exceptions import (
    LightCurveSourceSelectionError,
    SelectionError,
)
from etl.selectors.nearest_light_curve_source_selector import (
    NearestLightCurveSourceSelector,
    NearestSourceSelection,
)

__all__ = [
    "LightCurveSourceSelectionError",
    "NearestLightCurveSourceSelector",
    "NearestSourceSelection",
    "SelectionError",
]