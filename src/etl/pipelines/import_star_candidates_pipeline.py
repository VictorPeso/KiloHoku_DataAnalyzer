"""
Pipeline de importación de candidatos estelares.

Esta pipeline coordina tres etapas:

    Extractor
        ↓
    pandas.DataFrame
        ↓
    StarCandidateTransformer
        ↓
    list[StarCandidate]
        ↓
    StarCandidateValidator
        ↓
    candidatos válidos e inválidos

La pipeline no implementa directamente la extracción, transformación ni
validación. Su responsabilidad es coordinar esos componentes y producir un
resultado completo de la ejecución.
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
from etl.validators import (
    StarCandidateValidator,
    ValidationResult,
)


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CandidateValidationRecord:
    """
    Relaciona un candidato con su resultado de validación.

    Attributes:
        candidate:
            Candidato que ha sido validado.

        validation_result:
            Errores, advertencias e información encontrados durante
            la validación.
    """

    candidate: StarCandidate
    validation_result: ValidationResult

    @property
    def is_valid(self) -> bool:
        """
        Indica si el candidato ha superado la validación.
        """

        return self.validation_result.is_valid


@dataclass(frozen=True, slots=True)
class ImportStarCandidatesResult:
    """
    Resultado completo de la pipeline de importación.

    Attributes:
        candidates:
            Todos los candidatos transformados, tanto válidos como inválidos.

        valid_candidates:
            Candidatos que no contienen errores bloqueantes de validación.

        invalid_candidates:
            Candidatos que contienen al menos un error bloqueante.

        validation_records:
            Relación entre cada candidato y su resultado de validación.

        extracted_rows:
            Número total de filas obtenidas desde la fuente.

        transformed_rows:
            Número de filas convertidas correctamente a StarCandidate.

        transformation_invalid_rows:
            Número de filas que no pudieron transformarse.

        validation_valid_rows:
            Número de candidatos que superaron la validación.

        validation_invalid_rows:
            Número de candidatos que no superaron la validación.

        validation_error_count:
            Número total de errores de validación encontrados.

        validation_warning_count:
            Número total de advertencias de validación encontradas.

        validation_info_count:
            Número total de incidencias informativas.

        elapsed_seconds:
            Tiempo total empleado por la pipeline.
    """

    candidates: list[StarCandidate]
    valid_candidates: list[StarCandidate]
    invalid_candidates: list[StarCandidate]
    validation_records: list[CandidateValidationRecord]

    extracted_rows: int
    transformed_rows: int
    transformation_invalid_rows: int

    validation_valid_rows: int
    validation_invalid_rows: int

    validation_error_count: int
    validation_warning_count: int
    validation_info_count: int

    elapsed_seconds: float

    @property
    def has_transformation_errors(self) -> bool:
        """
        Indica si alguna fila no pudo transformarse.
        """

        return self.transformation_invalid_rows > 0

    @property
    def has_validation_errors(self) -> bool:
        """
        Indica si algún candidato no superó la validación.
        """

        return self.validation_invalid_rows > 0

    @property
    def has_warnings(self) -> bool:
        """
        Indica si se generó alguna advertencia.
        """

        return self.validation_warning_count > 0

    @property
    def transformation_success_rate(self) -> float:
        """
        Porcentaje de filas transformadas correctamente.
        """

        if self.extracted_rows == 0:
            return 0.0

        return (
            self.transformed_rows
            / self.extracted_rows
        ) * 100.0

    @property
    def validation_success_rate(self) -> float:
        """
        Porcentaje de candidatos transformados que superaron la validación.
        """

        if self.transformed_rows == 0:
            return 0.0

        return (
            self.validation_valid_rows
            / self.transformed_rows
        ) * 100.0

    @property
    def overall_success_rate(self) -> float:
        """
        Porcentaje de filas extraídas que terminaron como candidatos válidos.
        """

        if self.extracted_rows == 0:
            return 0.0

        return (
            self.validation_valid_rows
            / self.extracted_rows
        ) * 100.0


class ImportStarCandidatesPipeline:
    """
    Coordina la extracción, transformación y validación de candidatos.

    La pipeline recibe sus dependencias desde el exterior para evitar
    depender de implementaciones concretas.

    Esto permite sustituir componentes en el futuro, por ejemplo:

        CsvExtractor por XmlExtractor
        StarCandidateValidator por otro validator especializado
    """

    def __init__(
        self,
        *,
        extractor: BaseExtractor[pd.DataFrame],
        transformer: StarCandidateTransformer,
        validator: StarCandidateValidator,
    ) -> None:
        """
        Inicializa la pipeline.

        Args:
            extractor:
                Componente encargado de extraer los datos y devolver un
                pandas.DataFrame.

            transformer:
                Componente encargado de convertir cada fila en una entidad
                StarCandidate.

            validator:
                Componente encargado de validar la calidad y coherencia de
                cada StarCandidate.
        """

        self._extractor = extractor
        self._transformer = transformer
        self._validator = validator

    def run(
        self,
        *,
        skip_invalid_transformation_rows: bool = False,
        skip_invalid_validation_candidates: bool = True,
    ) -> ImportStarCandidatesResult:
        """
        Ejecuta la pipeline completa.

        Args:
            skip_invalid_transformation_rows:
                Si es False, una fila que no pueda transformarse detendrá
                la ejecución.

                Si es True, la fila será registrada y omitida.

            skip_invalid_validation_candidates:
                Si es True, los candidatos que no superen la validación no
                aparecerán en ``valid_candidates``, pero la pipeline
                continuará y quedarán disponibles en ``invalid_candidates``.

                Si es False, la primera validación con errores detendrá la
                pipeline mediante TransformationError.

        Returns:
            Resultado completo de extracción, transformación y validación.

        Raises:
            ExtractionError:
                Si la etapa de extracción falla.

            TransformationError:
                Si la transformación falla y no se permite omitir filas, o
                si la validación falla y no se permite continuar.
        """

        start_time = perf_counter()

        logger.info(
            "Iniciando pipeline de importación. "
            "extractor=%s transformer=%s validator=%s "
            "skip_invalid_transformation_rows=%s "
            "skip_invalid_validation_candidates=%s",
            type(self._extractor).__name__,
            type(self._transformer).__name__,
            type(self._validator).__name__,
            skip_invalid_transformation_rows,
            skip_invalid_validation_candidates,
        )

        try:
            dataframe = self._extract()

            candidates = self._transform(
                dataframe,
                skip_invalid_rows=skip_invalid_transformation_rows,
            )

            validation_records = self._validate(
                candidates,
                skip_invalid_candidates=(
                    skip_invalid_validation_candidates
                ),
            )

        except ExtractionError:
            logger.exception(
                "La pipeline ha fallado durante la extracción."
            )
            raise

        except TransformationError:
            logger.exception(
                "La pipeline ha fallado durante la transformación "
                "o validación."
            )
            raise

        elapsed_seconds = perf_counter() - start_time

        valid_candidates = [
            record.candidate
            for record in validation_records
            if record.is_valid
        ]

        invalid_candidates = [
            record.candidate
            for record in validation_records
            if not record.is_valid
        ]

        extracted_rows = len(dataframe)
        transformed_rows = len(candidates)

        validation_error_count = sum(
            record.validation_result.error_count
            for record in validation_records
        )

        validation_warning_count = sum(
            record.validation_result.warning_count
            for record in validation_records
        )

        validation_info_count = sum(
            record.validation_result.info_count
            for record in validation_records
        )

        result = ImportStarCandidatesResult(
            candidates=candidates,
            valid_candidates=valid_candidates,
            invalid_candidates=invalid_candidates,
            validation_records=validation_records,
            extracted_rows=extracted_rows,
            transformed_rows=transformed_rows,
            transformation_invalid_rows=(
                extracted_rows - transformed_rows
            ),
            validation_valid_rows=len(valid_candidates),
            validation_invalid_rows=len(invalid_candidates),
            validation_error_count=validation_error_count,
            validation_warning_count=validation_warning_count,
            validation_info_count=validation_info_count,
            elapsed_seconds=elapsed_seconds,
        )

        logger.info(
            "Pipeline de importación completada. "
            "extracted_rows=%d transformed_rows=%d "
            "transformation_invalid_rows=%d "
            "validation_valid_rows=%d validation_invalid_rows=%d "
            "validation_errors=%d validation_warnings=%d "
            "validation_info=%d transformation_success_rate=%.2f "
            "validation_success_rate=%.2f overall_success_rate=%.2f "
            "elapsed_seconds=%.4f",
            result.extracted_rows,
            result.transformed_rows,
            result.transformation_invalid_rows,
            result.validation_valid_rows,
            result.validation_invalid_rows,
            result.validation_error_count,
            result.validation_warning_count,
            result.validation_info_count,
            result.transformation_success_rate,
            result.validation_success_rate,
            result.overall_success_rate,
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
                Datos obtenidos desde el extractor.

            skip_invalid_rows:
                Indica si las filas que no puedan transformarse deben
                omitirse.

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

    def _validate(
        self,
        candidates: list[StarCandidate],
        *,
        skip_invalid_candidates: bool,
    ) -> list[CandidateValidationRecord]:
        """
        Ejecuta la etapa de validación.

        Args:
            candidates:
                Candidatos transformados.

            skip_invalid_candidates:
                Si es False, el primer candidato inválido detiene
                la pipeline.

        Returns:
            Registros que relacionan cada candidato con su resultado.

        Raises:
            TransformationError:
                Si un candidato no supera la validación y no se permite
                continuar.
        """

        logger.info(
            "Iniciando validación de candidatos. candidates=%d "
            "skip_invalid_candidates=%s",
            len(candidates),
            skip_invalid_candidates,
        )

        validation_records: list[CandidateValidationRecord] = []

        valid_count = 0
        invalid_count = 0
        warning_count = 0

        for candidate in candidates:
            validation_result = self._validator.validate(candidate)

            record = CandidateValidationRecord(
                candidate=candidate,
                validation_result=validation_result,
            )

            validation_records.append(record)

            warning_count += validation_result.warning_count

            if validation_result.is_valid:
                valid_count += 1
                continue

            invalid_count += 1

            logger.error(
                "Candidato no válido. alert_id=%s errors=%d "
                "warnings=%d",
                candidate.alert_id,
                validation_result.error_count,
                validation_result.warning_count,
            )

            for issue in validation_result.errors:
                logger.error(
                    "Error de validación. alert_id=%s code=%s "
                    "field=%s value=%r message=%s",
                    candidate.alert_id,
                    issue.code,
                    issue.field_name,
                    issue.value,
                    issue.message,
                )

            if not skip_invalid_candidates:
                raise TransformationError(
                    "Un candidato no ha superado la validación.",
                    field_name="star_candidate",
                    raw_value=candidate.alert_id,
                )

        logger.info(
            "Validación de candidatos completada. valid=%d invalid=%d "
            "warnings=%d",
            valid_count,
            invalid_count,
            warning_count,
        )

        return validation_records