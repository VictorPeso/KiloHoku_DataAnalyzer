"""
Excepciones relacionadas con la extracción de datos.

Estas excepciones permiten distinguir los errores de lectura de archivos
de los errores producidos durante la transformación o validación.
"""

from __future__ import annotations


class ExtractionError(RuntimeError):
    """
    Error general producido durante la extracción de datos.
    """


class SourceFileNotFoundError(ExtractionError):
    """
    Indica que el archivo de origen no existe.
    """


class InvalidCsvStructureError(ExtractionError):
    """
    Indica que el CSV no tiene la estructura esperada.
    """