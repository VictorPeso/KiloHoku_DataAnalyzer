"""
Contratos base para los extractores del proceso ETL.

Este módulo define la interfaz común que deben implementar los extractores,
independientemente de si obtienen los datos desde un archivo, una API, una
base de datos u otra fuente.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar


ExtractedData = TypeVar("ExtractedData")


class BaseExtractor(ABC, Generic[ExtractedData]):
    """
    Clase base abstracta para todos los extractores.

    ``ExtractedData`` representa el tipo de dato devuelto por el extractor.

    Ejemplos:

        BaseExtractor[pandas.DataFrame]
        BaseExtractor[list[dict[str, object]]]
        BaseExtractor[bytes]

    Las clases que hereden de BaseExtractor deben implementar el método
    ``extract``.
    """

    @abstractmethod
    def extract(self) -> ExtractedData:
        """
        Extrae los datos desde la fuente configurada.

        Returns:
            Datos obtenidos desde la fuente.

        Raises:
            ExtractionError:
                Si los datos no pueden extraerse correctamente.
        """

        raise NotImplementedError