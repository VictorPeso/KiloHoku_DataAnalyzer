"""
Excepciones relacionadas con la selección de elementos.
"""

from __future__ import annotations


class SelectionError(ValueError):
    """
    Error base producido durante un proceso de selección.
    """


class LightCurveSourceSelectionError(SelectionError):
    """
    Error producido al seleccionar una fuente de curva de luz.

    Se utiliza cuando no puede aplicarse correctamente el criterio de
    selección sobre las fuentes candidatas.
    """