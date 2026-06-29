"""
Pipeline de importación de candidatos estelares.

Esta pipeline coordina la extracción y transformación de los candidatos
astronómicos procedentes de una fuente tabular.

Flujo actual:

    Extractor
        ↓
    pandas.DataFrame
        ↓
    StarCandidateTransformer
        ↓
    list[StarCandidate]

La pipeline no conoce los detalles internos del archivo CSV ni realiza
conversiones de campos. Esas responsabilidades pertenecen respectivamente
al extractor y al transformer.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import pandas as pd

from etl.domain.entities import StarCandidate
from etl.extractors.base import BaseExtractor
from etl.extractors.exceptions import ExtractionError
from etl.logger import get_logger
from etl.transformers import (
    StarCandidateTransformer,
    TransformationError,
)


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ImportStarCandidatesResult:
    """
    Resultado generado por la pipeline de importación.

    Attributes:
        candidates:
            Candidatos transformados correctamente.

        extracted_rows:
            Número total de filas extraídas desde la fuente.

        valid_rows:
            Número de filas transformadas correctamente.

        invalid_rows:
            Número de filas que no pudieron transformarse.

        elapsed_seconds:
            Tiempo total empleado por la pipeline.
    """

    candidates: list[StarCandidate]
    extracted_rows: int
    valid_rows: int
    invalid_rows: int
    elapsed_seconds: float

    @property
    def has_invalid_rows(self) -> bool:
        """
        Indica si se encontró alguna fila inválida.
        """

        return self.invalid_rows > 0

    @property
    def success_rate(self) -> float:
        """
        Calcula el porcentaje de filas transformadas correctamente.

        Returns:
            Porcentaje comprendido entre 0 y 100.
        """

        if self.extracted_rows == 0:
            return 0.0

        return (self.valid_rows / self.extracted_rows) * 100.0


class ImportStarCandidatesPipeline:
    """
    Coordina la extracción y transformación de candidatos estelares.

    La pipeline recibe sus dependencias desde el exterior. Esto permite
    sustituir el extractor sin modificar su implementación.

    Por ejemplo, en el futuro podría trabajar con:

        CsvExtractor
        XmlExtractor
        ApiExtractor

    siempre que el extractor devuelva un pandas.DataFrame.
    """

    def __init__(
        self,
        *,
        extractor: BaseExtractor[pd.DataFrame],
        transformer: StarCandidateTransformer,
    ) -> None:
        """
        Inicializa la pipeline.

        Args:
            extractor:
                Componente encargado de obtener los datos y devolver un
                pandas.DataFrame.

            transformer:
                Componente encargado de convertir las filas del DataFrame
                en entidades StarCandidate.
        """

        self._extractor = extractor
        self._transformer = transformer

    def run(
        self,
        *,
        skip_invalid_rows: bool = False,
    ) -> ImportStarCandidatesResult:
        """
        Ejecuta el proceso de extracción y transformación.

        Args:
            skip_invalid_rows:
                Si es False, la primera fila inválida detiene la pipeline.

                Si es True, las filas inválidas se registran y se omiten,
                permitiendo continuar con el resto del DataFrame.

        Returns:
            Resultado completo de la ejecución.

        Raises:
            ExtractionError:
                Si no pueden extraerse los datos desde la fuente.

            TransformationError:
                Si los datos no pueden transformarse y
                ``skip_invalid_rows`` es False.
        """

        start_time = perf_counter()

        logger.info(
            "Iniciando pipeline de importación de candidatos. "
            "extractor=%s transformer=%s skip_invalid_rows=%s",
            type(self._extractor).__name__,
            type(self._transformer).__name__,
            skip_invalid_rows,
        )

        try:
            dataframe = self._extract()

            candidates = self._transform(
                dataframe,
                skip_invalid_rows=skip_invalid_rows,
            )

        except ExtractionError:
            logger.exception(
                "La pipeline ha fallado durante la extracción."
            )
            raise

        except TransformationError:
            logger.exception(
                "La pipeline ha fallado durante la transformación."
            )
            raise

        elapsed_seconds = perf_counter() - start_time
        extracted_rows = len(dataframe)
        valid_rows = len(candidates)
        invalid_rows = extracted_rows - valid_rows

        result = ImportStarCandidatesResult(
            candidates=candidates,
            extracted_rows=extracted_rows,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            elapsed_seconds=elapsed_seconds,
        )

        logger.info(
            "Pipeline de importación completada. "
            "extracted_rows=%d valid_rows=%d invalid_rows=%d "
            "success_rate=%.2f elapsed_seconds=%.4f",
            result.extracted_rows,
            result.valid_rows,
            result.invalid_rows,
            result.success_rate,
            result.elapsed_seconds,
        )

        return result

    def _extract(self) -> pd.DataFrame:
        """
        Ejecuta la etapa de extracción.

        Returns:
            DataFrame obtenido desde la fuente.

        Raises:
            ExtractionError:
                Si el extractor no puede obtener los datos.

            TypeError:
                Si el extractor devuelve un tipo inesperado.
        """

        logger.debug(
            "Ejecutando etapa de extracción. extractor=%s",
            type(self._extractor).__name__,
        )

        dataframe = self._extractor.extract()

        if not isinstance(dataframe, pd.DataFrame):
            logger.error(
                "El extractor ha devuelto un tipo inesperado. "
                "expected=%s received=%s",
                pd.DataFrame.__name__,
                type(dataframe).__name__,
            )

            raise TypeError(
                "El extractor debe devolver un pandas.DataFrame. "
                f"Tipo recibido: {type(dataframe).__name__}."
            )

        logger.debug(
            "Etapa de extracción completada. rows=%d columns=%d",
            len(dataframe),
            len(dataframe.columns),
        )

        return dataframe

    def _transform(
        self,
        dataframe: pd.DataFrame,
        *,
        skip_invalid_rows: bool,
    ) -> list[StarCandidate]:
        """
        Ejecuta la etapa de transformación.

        Args:
            dataframe:
                Datos extraídos.

            skip_invalid_rows:
                Indica si deben omitirse las filas inválidas.

        Returns:
            Lista de candidatos transformados.
        """

        logger.debug(
            "Ejecutando etapa de transformación. rows=%d",
            len(dataframe),
        )

        candidates = self._transformer.transform(
            dataframe,
            skip_invalid_rows=skip_invalid_rows,
        )

        logger.debug(
            "Etapa de transformación completada. candidates=%d",
            len(candidates),
        )

        return candidates