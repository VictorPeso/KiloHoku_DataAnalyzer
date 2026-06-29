"""
Transformer de candidatos estelares.

Convierte las filas de un pandas.DataFrame en entidades StarCandidate
validadas y listas para utilizarse en el dominio.
"""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Final

import pandas as pd

from etl.domain.entities import StarCandidate
from etl.logger import get_logger
from etl.transformers.exceptions import TransformationError


logger = get_logger(__name__)


class StarCandidateTransformer:
    """
    Convierte datos tabulares de pandas en entidades StarCandidate.
    """

    REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
        "alert",
        "date",
        "ra",
        "dec",
        "closest_simbad_target",
        "class",
        "angdist",
        "dr3name",
        "gmag",
        "bpmag",
        "rpmag",
        "plx",
        "plx_err",
        "wd_zone",
        "spectrum",
        "emission",
        "file",
        "plot",
    )

    TRUE_VALUES: Final[frozenset[str]] = frozenset(
        {
            "true",
            "1",
            "yes",
            "y",
            "si",
            "sí",
        }
    )

    FALSE_VALUES: Final[frozenset[str]] = frozenset(
        {
            "false",
            "0",
            "no",
            "n",
        }
    )

    def transform(
        self,
        dataframe: pd.DataFrame,
        *,
        skip_invalid_rows: bool = False,
    ) -> list[StarCandidate]:
        """
        Convierte todas las filas del DataFrame en entidades.

        Args:
            dataframe:
                Datos obtenidos mediante CsvExtractor.

            skip_invalid_rows:
                Si es False, la primera fila inválida detiene la operación.

                Si es True, las filas inválidas se registran como errores y
                se omiten, permitiendo procesar las demás.

        Returns:
            Lista de entidades StarCandidate válidas.

        Raises:
            TransformationError:
                Si el DataFrame tiene una estructura inválida o alguna fila
                no puede transformarse y ``skip_invalid_rows`` es False.
        """

        self._validate_dataframe(dataframe)

        logger.info(
            "Iniciando transformación de candidatos. rows=%d "
            "skip_invalid_rows=%s",
            len(dataframe),
            skip_invalid_rows,
        )

        candidates: list[StarCandidate] = []
        invalid_rows = 0

        for dataframe_index, row in dataframe.iterrows():
            # La cabecera ocupa la fila 1. Por tanto, el índice 0 del
            # DataFrame corresponde a la fila 2 del archivo CSV.
            row_number = self._calculate_csv_row_number(
                dataframe_index
            )

            try:
                candidate = self.transform_row(
                    row,
                    row_number=row_number,
                )
            except TransformationError:
                invalid_rows += 1

                logger.exception(
                    "No se pudo transformar una fila del CSV. row=%d",
                    row_number,
                )

                if not skip_invalid_rows:
                    raise

                continue

            candidates.append(candidate)

        logger.info(
            "Transformación completada. valid_rows=%d invalid_rows=%d",
            len(candidates),
            invalid_rows,
        )

        return candidates

    def transform_row(
        self,
        row: pd.Series,
        *,
        row_number: int | None = None,
    ) -> StarCandidate:
        """
        Convierte una fila de pandas en una entidad StarCandidate.

        Args:
            row:
                Fila del DataFrame.

            row_number:
                Número real de fila del archivo CSV.

        Returns:
            Entidad StarCandidate validada.

        Raises:
            TransformationError:
                Si algún campo no puede convertirse o la entidad resultante
                incumple las reglas del dominio.
        """

        try:
            candidate = StarCandidate(
                alert_url=self._parse_required_string(
                    row.get("alert"),
                    field_name="alert",
                    row_number=row_number,
                ),
                observation_date=self._parse_datetime(
                    row.get("date"),
                    field_name="date",
                    row_number=row_number,
                ),
                right_ascension=self._parse_required_float(
                    row.get("ra"),
                    field_name="ra",
                    row_number=row_number,
                ),
                declination=self._parse_required_float(
                    row.get("dec"),
                    field_name="dec",
                    row_number=row_number,
                ),
                closest_simbad_target=self._parse_optional_string(
                    row.get("closest_simbad_target")
                ),
                object_class=self._parse_optional_string(
                    row.get("class")
                ),
                angular_distance=self._parse_optional_float(
                    row.get("angdist"),
                    field_name="angdist",
                    row_number=row_number,
                ),
                gaia_dr3_name=self._parse_required_string(
                    row.get("dr3name"),
                    field_name="dr3name",
                    row_number=row_number,
                ),
                gaia_g_magnitude=self._parse_required_float(
                    row.get("gmag"),
                    field_name="gmag",
                    row_number=row_number,
                ),
                gaia_bp_magnitude=self._parse_required_float(
                    row.get("bpmag"),
                    field_name="bpmag",
                    row_number=row_number,
                ),
                gaia_rp_magnitude=self._parse_required_float(
                    row.get("rpmag"),
                    field_name="rpmag",
                    row_number=row_number,
                ),
                parallax=self._parse_required_float(
                    row.get("plx"),
                    field_name="plx",
                    row_number=row_number,
                ),
                parallax_error=self._parse_required_float(
                    row.get("plx_err"),
                    field_name="plx_err",
                    row_number=row_number,
                ),
                is_in_white_dwarf_zone=self._parse_required_bool(
                    row.get("wd_zone"),
                    field_name="wd_zone",
                    row_number=row_number,
                ),
                has_spectrum=self._parse_required_bool(
                    row.get("spectrum"),
                    field_name="spectrum",
                    row_number=row_number,
                ),
                has_emission=self._parse_required_bool(
                    row.get("emission"),
                    field_name="emission",
                    row_number=row_number,
                ),
                data_file_url=self._parse_optional_string(
                    row.get("file")
                ),
                plot_url=self._parse_optional_string(
                    row.get("plot")
                ),
            )

        except TransformationError:
            raise

        except (TypeError, ValueError) as error:
            raise TransformationError(
                "La entidad StarCandidate resultante no es válida.",
                row_number=row_number,
            ) from error

        return candidate

    @classmethod
    def _validate_dataframe(
        cls,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Comprueba que el objeto recibido sea un DataFrame válido.
        """

        if not isinstance(dataframe, pd.DataFrame):
            raise TransformationError(
                "El transformer esperaba un pandas.DataFrame."
            )

        missing_columns = [
            column
            for column in cls.REQUIRED_COLUMNS
            if column not in dataframe.columns
        ]

        if missing_columns:
            raise TransformationError(
                "El DataFrame no contiene todas las columnas requeridas: "
                f"{', '.join(missing_columns)}."
            )

        if dataframe.empty:
            raise TransformationError(
                "El DataFrame no contiene registros para transformar."
            )

    @staticmethod
    def _calculate_csv_row_number(
        dataframe_index: object,
    ) -> int:
        """
        Calcula el número de fila original del CSV.

        Para un RangeIndex normal:

            índice 0 -> fila 2
            índice 1 -> fila 3
        """

        if isinstance(dataframe_index, int):
            return dataframe_index + 2

        return 0

    @staticmethod
    def _is_missing(value: object) -> bool:
        """
        Indica si un valor está ausente según pandas.
        """

        if value is None:
            return True

        try:
            missing_result = pd.isna(value)
        except (TypeError, ValueError):
            return False

        return bool(missing_result)

    @classmethod
    def _parse_required_string(
        cls,
        value: object,
        *,
        field_name: str,
        row_number: int | None,
    ) -> str:
        """
        Convierte un valor obligatorio a string no vacío.
        """

        if cls._is_missing(value):
            raise TransformationError(
                "El campo de texto obligatorio no tiene valor.",
                field_name=field_name,
                row_number=row_number,
            )

        normalized_value = str(value).strip()

        if not normalized_value:
            raise TransformationError(
                "El campo de texto obligatorio está vacío.",
                field_name=field_name,
                raw_value=value,
                row_number=row_number,
            )

        return normalized_value

    @classmethod
    def _parse_optional_string(
        cls,
        value: object,
    ) -> str | None:
        """
        Convierte un valor opcional a string o None.
        """

        if cls._is_missing(value):
            return None

        normalized_value = str(value).strip()

        return normalized_value or None

    @classmethod
    def _parse_required_float(
        cls,
        value: object,
        *,
        field_name: str,
        row_number: int | None,
    ) -> float:
        """
        Convierte un valor obligatorio a float finito.
        """

        if cls._is_missing(value):
            raise TransformationError(
                "El campo numérico obligatorio no tiene valor.",
                field_name=field_name,
                row_number=row_number,
            )

        try:
            parsed_value = float(value)
        except (TypeError, ValueError) as error:
            raise TransformationError(
                "El valor no se puede convertir a float.",
                field_name=field_name,
                raw_value=value,
                row_number=row_number,
            ) from error

        if not isfinite(parsed_value):
            raise TransformationError(
                "El valor numérico debe ser finito.",
                field_name=field_name,
                raw_value=value,
                row_number=row_number,
            )

        return parsed_value

    @classmethod
    def _parse_optional_float(
        cls,
        value: object,
        *,
        field_name: str,
        row_number: int | None,
    ) -> float | None:
        """
        Convierte un valor opcional a float o None.
        """

        if cls._is_missing(value):
            return None

        return cls._parse_required_float(
            value,
            field_name=field_name,
            row_number=row_number,
        )

    @classmethod
    def _parse_required_bool(
        cls,
        value: object,
        *,
        field_name: str,
        row_number: int | None,
    ) -> bool:
        """
        Convierte un valor obligatorio a bool.

        Soporta booleanos reales, 0, 1 y sus representaciones textuales.
        """

        if cls._is_missing(value):
            raise TransformationError(
                "El campo booleano obligatorio no tiene valor.",
                field_name=field_name,
                row_number=row_number,
            )

        # pandas suele devolver bool o numpy.bool_ en estas columnas.
        if isinstance(value, bool):
            return value

        normalized_value = str(value).strip().lower()

        if normalized_value in cls.TRUE_VALUES:
            return True

        if normalized_value in cls.FALSE_VALUES:
            return False

        raise TransformationError(
            "El valor no representa un booleano válido.",
            field_name=field_name,
            raw_value=value,
            row_number=row_number,
        )

    @classmethod
    def _parse_datetime(
        cls,
        value: object,
        *,
        field_name: str,
        row_number: int | None,
    ) -> datetime:
        """
        Convierte un valor a datetime.

        Acepta strings compatibles con pandas y objetos Timestamp.
        """

        if cls._is_missing(value):
            raise TransformationError(
                "El campo de fecha obligatorio no tiene valor.",
                field_name=field_name,
                row_number=row_number,
            )

        if isinstance(value, datetime):
            return value

        try:
            parsed_date = pd.to_datetime(
                value,
                errors="raise",
            )
        except (TypeError, ValueError) as error:
            raise TransformationError(
                "El valor no representa una fecha válida.",
                field_name=field_name,
                raw_value=value,
                row_number=row_number,
            ) from error

        if pd.isna(parsed_date):
            raise TransformationError(
                "El valor no representa una fecha válida.",
                field_name=field_name,
                raw_value=value,
                row_number=row_number,
            )

        return parsed_date.to_pydatetime()