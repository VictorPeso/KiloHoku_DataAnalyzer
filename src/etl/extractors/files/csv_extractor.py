"""
Extractor de candidatos estelares desde archivos CSV.

Este módulo se encarga únicamente de:

- Localizar el archivo de entrada.
- Leerlo mediante pandas.
- Comprobar que contiene las columnas esperadas.
- Devolver un DataFrame con los datos extraídos.

No convierte las filas en entidades de dominio. Esa responsabilidad
corresponde al transformer.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pandas as pd

from etl.extractors.base import BaseExtractor
from etl.extractors.exceptions import (
    ExtractionError,
    InvalidCsvStructureError,
    SourceFileNotFoundError,
)
from etl.logger import get_logger


logger = get_logger(__name__)


class CsvExtractor(BaseExtractor[pd.DataFrame]):
    """
    Extrae candidatos estelares desde un archivo CSV.

    Attributes:
        file_path:
            Ruta absoluta del archivo que debe leerse.
    """

    EXPECTED_COLUMNS: Final[tuple[str, ...]] = (
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

    def __init__(
        self,
        file_path: str | Path,
        *,
        encoding: str = "utf-8-sig",
        delimiter: str = ",",
    ) -> None:
        """
        Inicializa el extractor.

        Args:
            file_path:
                Ruta del archivo CSV.

            encoding:
                Codificación utilizada para leer el archivo. ``utf-8-sig``
                también elimina automáticamente una posible marca BOM.

            delimiter:
                Carácter utilizado como separador de columnas.
        """

        self._file_path = Path(file_path).expanduser().resolve()
        self._encoding = encoding
        self._delimiter = delimiter

    @property
    def file_path(self) -> Path:
        """
        Devuelve la ruta absoluta del archivo de entrada.
        """

        return self._file_path

    def extract(self) -> pd.DataFrame:
        """
        Lee y valida estructuralmente el archivo CSV.

        Returns:
            DataFrame con las columnas originales de resultados.csv.

        Raises:
            SourceFileNotFoundError:
                Si el archivo no existe.

            InvalidCsvStructureError:
                Si el CSV está vacío, no tiene cabecera o le faltan columnas.

            ExtractionError:
                Si pandas no puede leer el archivo.
        """

        logger.info(
            "Iniciando extracción del archivo CSV. file=%s",
            self._file_path,
        )

        self._validate_source_file()

        try:
            dataframe = pd.read_csv(
                self._file_path,
                sep=self._delimiter,
                encoding=self._encoding,
                keep_default_na=True,
                na_values=["", "null", "NULL", "None"],
            )
        except pd.errors.EmptyDataError as error:
            logger.exception(
                "El archivo CSV está vacío. file=%s",
                self._file_path,
            )

            raise InvalidCsvStructureError(
                f"El archivo CSV está vacío: {self._file_path}"
            ) from error

        except pd.errors.ParserError as error:
            logger.exception(
                "No se pudo interpretar la estructura del CSV. file=%s",
                self._file_path,
            )

            raise InvalidCsvStructureError(
                "No se pudo interpretar la estructura del archivo CSV: "
                f"{self._file_path}"
            ) from error

        except (OSError, UnicodeError) as error:
            logger.exception(
                "No se pudo leer el archivo CSV. file=%s",
                self._file_path,
            )

            raise ExtractionError(
                f"No se pudo leer el archivo CSV: {self._file_path}"
            ) from error

        self._validate_columns(dataframe.columns)
        self._validate_not_empty(dataframe)

        logger.info(
            "Extracción del CSV completada. file=%s rows=%d columns=%d",
            self._file_path,
            len(dataframe),
            len(dataframe.columns),
        )

        return dataframe

    def _validate_source_file(self) -> None:
        """
        Comprueba que la ruta representa un archivo accesible.

        Raises:
            SourceFileNotFoundError:
                Si la ruta no existe o no representa un archivo.
        """

        if not self._file_path.exists():
            logger.error(
                "El archivo CSV no existe. file=%s",
                self._file_path,
            )

            raise SourceFileNotFoundError(
                f"El archivo CSV no existe: {self._file_path}"
            )

        if not self._file_path.is_file():
            logger.error(
                "La ruta de entrada no representa un archivo. file=%s",
                self._file_path,
            )

            raise SourceFileNotFoundError(
                "La ruta de entrada no representa un archivo: "
                f"{self._file_path}"
            )

    def _validate_columns(
        self,
        actual_columns: Sequence[str],
    ) -> None:
        """
        Comprueba que el CSV contenga las columnas necesarias.

        Se permiten columnas adicionales, pero no pueden faltar columnas
        obligatorias.

        Args:
            actual_columns:
                Nombres de las columnas detectadas por pandas.

        Raises:
            InvalidCsvStructureError:
                Si falta alguna columna.
        """

        normalized_columns = {
            str(column).strip()
            for column in actual_columns
        }

        missing_columns = [
            column
            for column in self.EXPECTED_COLUMNS
            if column not in normalized_columns
        ]

        if not missing_columns:
            return

        formatted_columns = ", ".join(missing_columns)

        logger.error(
            "El CSV no contiene todas las columnas requeridas. "
            "file=%s missing_columns=%s",
            self._file_path,
            formatted_columns,
        )

        raise InvalidCsvStructureError(
            "El archivo CSV no contiene todas las columnas requeridas. "
            f"Columnas ausentes: {formatted_columns}."
        )

    def _validate_not_empty(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Comprueba que el CSV contenga al menos un registro.

        Args:
            dataframe:
                DataFrame leído.

        Raises:
            InvalidCsvStructureError:
                Si no contiene filas.
        """

        if not dataframe.empty:
            return

        logger.error(
            "El CSV contiene una cabecera pero ningún registro. file=%s",
            self._file_path,
        )

        raise InvalidCsvStructureError(
            "El archivo CSV no contiene ningún registro: "
            f"{self._file_path}"
        )