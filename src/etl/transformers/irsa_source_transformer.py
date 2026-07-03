"""
Transformer de resultados posicionales de NASA/IPAC IRSA.

Una consulta posicional a la API de curvas de luz ZTF puede devolver muchas
observaciones pertenecientes a distintos objetos y bandas fotométricas.

Este transformer convierte esa tabla de observaciones en una colección de
entidades ``IrsaLightCurveSource``.

El proceso realizado es:

    filas de IRSA
        ↓
    normalización de nombres y tipos
        ↓
    agrupación por oid y banda
        ↓
    cálculo de coordenadas representativas
        ↓
    recuento de observaciones totales y limpias
        ↓
    cálculo de separación angular
        ↓
    list[IrsaLightCurveSource]

Este componente no selecciona la mejor fuente. Esa responsabilidad pertenece
al selector correspondiente.
"""

from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Final

import pandas as pd

from etl.domain.entities import IrsaLightCurveSource
from etl.domain.value_objects import PhotometricBand
from etl.logger import get_logger
from etl.math import angular_separation_arcsec
from etl.transformers.exceptions import (
    IrsaSourceTransformationError,
)


logger = get_logger(__name__)


_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "oid",
        "filtercode",
        "ra",
        "dec",
        "catflags",
    }
)


class IrsaSourceTransformer:
    """
    Convierte observaciones tabulares de IRSA en fuentes candidatas.

    El transformer espera una fila por observación y agrupa los datos por:

        oid + banda fotométrica

    Cada grupo produce una entidad ``IrsaLightCurveSource``.
    """

    def transform(
        self,
        dataframe: pd.DataFrame,
        *,
        target_right_ascension: float,
        target_declination: float,
    ) -> list[IrsaLightCurveSource]:
        """
        Transforma una tabla de observaciones en fuentes candidatas.

        Args:
            dataframe:
                DataFrame con las observaciones devueltas por IRSA.

                Debe contener, como mínimo:

                - oid
                - filtercode
                - ra
                - dec
                - catflags

            target_right_ascension:
                Ascensión recta del punto estudiado, en grados.

            target_declination:
                Declinación del punto estudiado, en grados.

        Returns:
            Fuentes candidatas ordenadas por:

            1. Banda fotométrica.
            2. Distancia angular.
            3. Identificador ZTF.

        Raises:
            TypeError:
                Si ``dataframe`` no es un DataFrame.

            IrsaSourceTransformationError:
                Si la tabla no tiene la estructura esperada o contiene
                valores que no pueden transformarse.
        """

        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError(
                "dataframe debe ser una instancia de pandas.DataFrame."
            )

        normalized_target_ra = self._validate_right_ascension(
            target_right_ascension,
            field_name="target_right_ascension",
        )

        normalized_target_dec = self._validate_declination(
            target_declination,
            field_name="target_declination",
        )

        normalized_columns_dataframe = self._normalize_column_names(
            dataframe
        )

        self._validate_columns(normalized_columns_dataframe)

        if normalized_columns_dataframe.empty:
            logger.info(
                "La respuesta posicional de IRSA no contiene "
                "observaciones."
            )
            return []

        normalized_dataframe = self._normalize_dataframe(
            normalized_columns_dataframe
        )

        sources: list[IrsaLightCurveSource] = []

        grouped_observations = normalized_dataframe.groupby(
            ["oid", "band"],
            sort=False,
            dropna=False,
        )

        for (
            ztf_object_id,
            band_value,
        ), observations in grouped_observations:
            source = self._build_source(
                ztf_object_id=int(ztf_object_id),
                band=PhotometricBand.from_value(band_value),
                observations=observations,
                target_right_ascension=normalized_target_ra,
                target_declination=normalized_target_dec,
            )

            sources.append(source)

            logger.debug(
                "Fuente candidata de IRSA transformada. "
                "source_key=%s observations=%d "
                "clean_observations=%d distance_arcsec=%.6f",
                source.source_key,
                source.observation_count,
                source.clean_observation_count,
                source.angular_distance_arcsec,
            )

        sources.sort(
            key=lambda source: (
                source.band.value,
                source.angular_distance_arcsec,
                source.ztf_object_id,
            )
        )

        logger.info(
            "Transformación de fuentes IRSA completada. "
            "rows=%d sources=%d target_ra=%.8f target_dec=%.8f",
            len(normalized_dataframe),
            len(sources),
            normalized_target_ra,
            normalized_target_dec,
        )

        return sources

    @staticmethod
    def _normalize_column_names(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Devuelve una copia con los nombres de columna normalizados.

        Los nombres se convierten a minúsculas y se eliminan espacios
        exteriores.

        Raises:
            IrsaSourceTransformationError:
                Si dos columnas diferentes terminan teniendo el mismo nombre
                después de normalizarlas.
        """

        normalized_dataframe = dataframe.copy()

        normalized_columns = [
            str(column).strip().lower()
            for column in normalized_dataframe.columns
        ]

        if len(normalized_columns) != len(
            set(normalized_columns)
        ):
            raise IrsaSourceTransformationError(
                "La respuesta de IRSA contiene nombres de columna "
                "duplicados después de normalizarlos."
            )

        normalized_dataframe.columns = normalized_columns

        return normalized_dataframe

    @staticmethod
    def _validate_columns(
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Comprueba que estén presentes las columnas necesarias.
        """

        available_columns = set(dataframe.columns)

        missing_columns = (
            _REQUIRED_COLUMNS - available_columns
        )

        if not missing_columns:
            return

        formatted_columns = ", ".join(
            sorted(missing_columns)
        )

        raise IrsaSourceTransformationError(
            "La respuesta de IRSA no contiene todas las "
            f"columnas necesarias: {formatted_columns}."
        )

    def _normalize_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Copia y normaliza las columnas necesarias.

        Returns:
            DataFrame nuevo con tipos consistentes.
        """

        normalized = dataframe.loc[
            :,
            [
                "oid",
                "filtercode",
                "ra",
                "dec",
                "catflags",
            ],
        ].copy()

        normalized["oid"] = normalized["oid"].map(
            lambda value: self._parse_positive_integer(
                value,
                field_name="oid",
            )
        )

        normalized["filtercode"] = normalized[
            "filtercode"
        ].map(self._normalize_filter_code)

        normalized["band"] = normalized[
            "filtercode"
        ].map(
            lambda value: PhotometricBand.from_value(
                value
            ).value
        )

        normalized["ra"] = normalized["ra"].map(
            lambda value: self._validate_right_ascension(
                value,
                field_name="ra",
            )
        )

        normalized["dec"] = normalized["dec"].map(
            lambda value: self._validate_declination(
                value,
                field_name="dec",
            )
        )

        normalized["catflags"] = normalized[
            "catflags"
        ].map(
            lambda value: self._parse_non_negative_integer(
                value,
                field_name="catflags",
            )
        )

        return normalized

    def _build_source(
        self,
        *,
        ztf_object_id: int,
        band: PhotometricBand,
        observations: pd.DataFrame,
        target_right_ascension: float,
        target_declination: float,
    ) -> IrsaLightCurveSource:
        """
        Construye una fuente a partir de un grupo de observaciones.
        """

        if observations.empty:
            raise IrsaSourceTransformationError(
                "No se puede construir una fuente a partir "
                "de un grupo vacío."
            )

        source_right_ascension = (
            self._calculate_mean_right_ascension(
                observations["ra"]
            )
        )

        source_declination = self._calculate_mean_declination(
            observations["dec"]
        )

        observation_count = len(observations)

        clean_observation_count = int(
            observations["catflags"].eq(0).sum()
        )

        distance_arcsec = angular_separation_arcsec(
            target_right_ascension,
            target_declination,
            source_right_ascension,
            source_declination,
        )

        return IrsaLightCurveSource(
            ztf_object_id=ztf_object_id,
            band=band,
            right_ascension=source_right_ascension,
            declination=source_declination,
            observation_count=observation_count,
            clean_observation_count=clean_observation_count,
            angular_distance_arcsec=distance_arcsec,
        )

    @staticmethod
    def _calculate_mean_right_ascension(
        values: pd.Series,
    ) -> float:
        """
        Calcula la media circular de varias ascensiones rectas.

        Una media aritmética convencional falla cerca del límite 0°/360°.

        Por ejemplo, la media correcta de 359.9° y 0.1° es aproximadamente
        0°, no 180°.
        """

        if values.empty:
            raise IrsaSourceTransformationError(
                "No se puede calcular la ascensión recta media "
                "de una serie vacía."
            )

        radians = values.map(math.radians)

        mean_sine = float(
            radians.map(math.sin).mean()
        )

        mean_cosine = float(
            radians.map(math.cos).mean()
        )

        if math.isclose(
            mean_sine,
            0.0,
            abs_tol=1e-15,
        ) and math.isclose(
            mean_cosine,
            0.0,
            abs_tol=1e-15,
        ):
            raise IrsaSourceTransformationError(
                "No se ha podido calcular una ascensión recta "
                "representativa para la fuente."
            )

        mean_radians = math.atan2(
            mean_sine,
            mean_cosine,
        )

        return math.degrees(mean_radians) % 360.0

    @staticmethod
    def _calculate_mean_declination(
        values: pd.Series,
    ) -> float:
        """
        Calcula la declinación media de una fuente.
        """

        if values.empty:
            raise IrsaSourceTransformationError(
                "No se puede calcular la declinación media "
                "de una serie vacía."
            )

        mean_declination = float(values.mean())

        if not math.isfinite(mean_declination):
            raise IrsaSourceTransformationError(
                "No se ha podido calcular una declinación "
                "representativa para la fuente."
            )

        if not -90.0 <= mean_declination <= 90.0:
            raise IrsaSourceTransformationError(
                "La declinación media calculada está fuera del "
                "rango permitido.",
                field_name="dec",
                raw_value=mean_declination,
            )

        return mean_declination

    @staticmethod
    def _normalize_filter_code(
        value: object,
    ) -> str:
        """
        Normaliza y valida un código de filtro ZTF.

        Se aceptan:

            zg, zr, zi

        y también:

            g, r, i
        """

        if not isinstance(value, str):
            raise IrsaSourceTransformationError(
                "El código de filtro debe ser una cadena de texto.",
                field_name="filtercode",
                raw_value=value,
            )

        normalized_value = value.strip().lower()

        if not normalized_value:
            raise IrsaSourceTransformationError(
                "El código de filtro no puede estar vacío.",
                field_name="filtercode",
                raw_value=value,
            )

        try:
            PhotometricBand.from_value(normalized_value)
        except (TypeError, ValueError) as error:
            raise IrsaSourceTransformationError(
                "IRSA ha devuelto un código de filtro no soportado.",
                field_name="filtercode",
                raw_value=value,
            ) from error

        return normalized_value

    @classmethod
    def _parse_positive_integer(
        cls,
        value: object,
        *,
        field_name: str,
    ) -> int:
        """
        Convierte un valor en entero positivo.
        """

        normalized_value = cls._parse_integer(
            value,
            field_name=field_name,
        )

        if normalized_value <= 0:
            raise IrsaSourceTransformationError(
                "El valor debe ser mayor que cero.",
                field_name=field_name,
                raw_value=value,
            )

        return normalized_value

    @classmethod
    def _parse_non_negative_integer(
        cls,
        value: object,
        *,
        field_name: str,
    ) -> int:
        """
        Convierte un valor en entero no negativo.
        """

        normalized_value = cls._parse_integer(
            value,
            field_name=field_name,
        )

        if normalized_value < 0:
            raise IrsaSourceTransformationError(
                "El valor no puede ser negativo.",
                field_name=field_name,
                raw_value=value,
            )

        return normalized_value

    @staticmethod
    def _parse_integer(
        value: object,
        *,
        field_name: str,
    ) -> int:
        """
        Convierte un valor en entero.

        Admite:

        - Enteros Python o NumPy.
        - Flotantes que representen exactamente un entero.
        - Strings decimales.
        - Strings en notación hexadecimal.
        """

        if pd.isna(value):
            raise IrsaSourceTransformationError(
                "El valor no puede ser nulo.",
                field_name=field_name,
                raw_value=value,
            )

        if isinstance(value, bool):
            raise IrsaSourceTransformationError(
                "El valor no puede ser booleano.",
                field_name=field_name,
                raw_value=value,
            )

        if isinstance(value, Integral):
            return int(value)

        if isinstance(value, Real):
            numeric_value = float(value)

            if not math.isfinite(numeric_value):
                raise IrsaSourceTransformationError(
                    "El valor debe ser finito.",
                    field_name=field_name,
                    raw_value=value,
                )

            if not numeric_value.is_integer():
                raise IrsaSourceTransformationError(
                    "El valor debe representar un entero.",
                    field_name=field_name,
                    raw_value=value,
                )

            return int(numeric_value)

        if isinstance(value, str):
            normalized_value = value.strip()

            if not normalized_value:
                raise IrsaSourceTransformationError(
                    "El valor no puede estar vacío.",
                    field_name=field_name,
                    raw_value=value,
                )

            try:
                return int(normalized_value, 0)
            except ValueError:
                try:
                    numeric_value = float(
                        normalized_value
                    )
                except ValueError as error:
                    raise IrsaSourceTransformationError(
                        "El valor debe representar un entero.",
                        field_name=field_name,
                        raw_value=value,
                    ) from error

                if (
                    not math.isfinite(numeric_value)
                    or not numeric_value.is_integer()
                ):
                    raise IrsaSourceTransformationError(
                        "El valor debe representar un entero.",
                        field_name=field_name,
                        raw_value=value,
                    )

                return int(numeric_value)

        raise IrsaSourceTransformationError(
            "El valor debe representar un entero.",
            field_name=field_name,
            raw_value=value,
        )

    @classmethod
    def _validate_right_ascension(
        cls,
        value: object,
        *,
        field_name: str,
    ) -> float:
        """
        Valida una ascensión recta en el rango [0, 360).
        """

        normalized_value = cls._parse_real(
            value,
            field_name=field_name,
        )

        if not 0.0 <= normalized_value < 360.0:
            raise IrsaSourceTransformationError(
                "La ascensión recta debe estar en el rango [0, 360).",
                field_name=field_name,
                raw_value=value,
            )

        return normalized_value

    @classmethod
    def _validate_declination(
        cls,
        value: object,
        *,
        field_name: str,
    ) -> float:
        """
        Valida una declinación en el rango [-90, 90].
        """

        normalized_value = cls._parse_real(
            value,
            field_name=field_name,
        )

        if not -90.0 <= normalized_value <= 90.0:
            raise IrsaSourceTransformationError(
                "La declinación debe estar en el rango [-90, 90].",
                field_name=field_name,
                raw_value=value,
            )

        return normalized_value

    @staticmethod
    def _parse_real(
        value: object,
        *,
        field_name: str,
    ) -> float:
        """
        Convierte un valor en un número real finito.
        """

        if pd.isna(value):
            raise IrsaSourceTransformationError(
                "El valor no puede ser nulo.",
                field_name=field_name,
                raw_value=value,
            )

        if isinstance(value, bool):
            raise IrsaSourceTransformationError(
                "El valor no puede ser booleano.",
                field_name=field_name,
                raw_value=value,
            )

        if not isinstance(value, (Real, str)):
            raise IrsaSourceTransformationError(
                "El valor debe representar un número real.",
                field_name=field_name,
                raw_value=value,
            )

        try:
            normalized_value = float(value)
        except (TypeError, ValueError) as error:
            raise IrsaSourceTransformationError(
                "El valor debe representar un número real.",
                field_name=field_name,
                raw_value=value,
            ) from error

        if not math.isfinite(normalized_value):
            raise IrsaSourceTransformationError(
                "El valor debe ser un número finito.",
                field_name=field_name,
                raw_value=value,
            )

        return normalized_value