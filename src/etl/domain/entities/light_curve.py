"""
Entidad de dominio que representa una curva de luz ZTF.

Una curva de luz agrupa las observaciones fotométricas de un objeto ZTF
para una banda concreta:

    objeto ZTF + banda fotométrica + observaciones

Por ejemplo:

    oid=458116300003161
    band=g
    observations=(..., ..., ...)

Un mismo candidato puede tener varias curvas de luz:

    candidato
        ├── curva g
        ├── curva r
        └── curva i

La entidad no contiene identificadores propios de PostgreSQL. La relación
con el candidato y las claves internas de base de datos se gestionarán en
los modelos ORM.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean, median

from etl.domain.entities.light_curve_observation import (
    LightCurveObservation,
)
from etl.domain.value_objects import PhotometricBand


@dataclass(frozen=True, slots=True, kw_only=True)
class LightCurve:
    """
    Curva de luz de un objeto ZTF para una banda fotométrica.

    Attributes:
        ztf_object_id:
            Identificador del objeto dentro de ZTF, correspondiente al campo
            ``oid`` del VOTable.

        band:
            Banda fotométrica de la curva: g, r o i.

        source_right_ascension:
            Ascensión recta representativa del objeto devuelto por ZTF.

        source_declination:
            Declinación representativa del objeto devuelto por ZTF.

        search_right_ascension:
            Ascensión recta utilizada para realizar la consulta a IRSA.

        search_declination:
            Declinación utilizada para realizar la consulta a IRSA.

        search_radius_degrees:
            Radio de búsqueda utilizado en la consulta, expresado en grados.

        observations:
            Observaciones fotométricas que forman la curva.

        source_collection:
            Nombre del servicio o colección del que procede la curva.
    """

    ztf_object_id: int
    band: PhotometricBand

    source_right_ascension: float
    source_declination: float

    search_right_ascension: float
    search_declination: float
    search_radius_degrees: float

    observations: tuple[LightCurveObservation, ...]

    source_collection: str = "NASA/IPAC ZTF"

    def __post_init__(self) -> None:
        """
        Normaliza y valida los datos de la curva.

        Raises:
            TypeError:
                Si alguno de los atributos no tiene el tipo esperado.

            ValueError:
                Si un valor está fuera del rango permitido, la curva no
                contiene observaciones o sus datos son inconsistentes.
        """

        self._validate_required_integer(
            self.ztf_object_id,
            field_name="ztf_object_id",
            minimum=0,
        )

        normalized_band = PhotometricBand.from_value(self.band)

        object.__setattr__(
            self,
            "band",
            normalized_band,
        )

        self._validate_coordinate_pair(
            right_ascension=self.source_right_ascension,
            declination=self.source_declination,
            prefix="source",
        )

        self._validate_coordinate_pair(
            right_ascension=self.search_right_ascension,
            declination=self.search_declination,
            prefix="search",
        )

        self._validate_required_float(
            self.search_radius_degrees,
            field_name="search_radius_degrees",
            minimum=0.0,
            minimum_inclusive=False,
        )

        normalized_observations = self._normalize_observations(
            self.observations
        )

        object.__setattr__(
            self,
            "observations",
            normalized_observations,
        )

        normalized_source_collection = self._normalize_required_string(
            self.source_collection,
            field_name="source_collection",
        )

        object.__setattr__(
            self,
            "source_collection",
            normalized_source_collection,
        )

    @property
    def observation_count(self) -> int:
        """
        Devuelve el número de puntos de la curva.
        """

        return len(self.observations)

    @property
    def filter_code(self) -> str:
        """
        Devuelve el código de filtro usado en los VOTable ZTF.

        Returns:
            ``zg``, ``zr`` o ``zi``.
        """

        return self.band.ztf_filter_code

    @property
    def first_modified_julian_date(self) -> float:
        """
        Devuelve la fecha MJD de la primera observación.
        """

        return min(
            observation.modified_julian_date
            for observation in self.observations
        )

    @property
    def last_modified_julian_date(self) -> float:
        """
        Devuelve la fecha MJD de la última observación.
        """

        return max(
            observation.modified_julian_date
            for observation in self.observations
        )

    @property
    def time_span_days(self) -> float:
        """
        Devuelve la duración temporal cubierta por la curva, en días.
        """

        return (
            self.last_modified_julian_date
            - self.first_modified_julian_date
        )

    @property
    def minimum_magnitude(self) -> float:
        """
        Devuelve el menor valor numérico de magnitud de la curva.

        En la escala astronómica, una magnitud menor representa un objeto
        más brillante.
        """

        return min(
            observation.magnitude
            for observation in self.observations
        )

    @property
    def maximum_magnitude(self) -> float:
        """
        Devuelve el mayor valor numérico de magnitud de la curva.
        """

        return max(
            observation.magnitude
            for observation in self.observations
        )

    @property
    def magnitude_amplitude(self) -> float:
        """
        Devuelve el rango observado de magnitudes.

        Se calcula como:

            magnitud máxima - magnitud mínima

        Esta propiedad representa una amplitud simple sin aplicar limpieza,
        eliminación de valores atípicos ni correcciones científicas.
        """

        return self.maximum_magnitude - self.minimum_magnitude

    @property
    def mean_magnitude(self) -> float:
        """
        Devuelve la magnitud media de las observaciones.
        """

        return mean(
            observation.magnitude
            for observation in self.observations
        )

    @property
    def median_magnitude(self) -> float:
        """
        Devuelve la mediana de las magnitudes.
        """

        return median(
            observation.magnitude
            for observation in self.observations
        )

    @property
    def mean_magnitude_error(self) -> float:
        """
        Devuelve el error de magnitud medio.
        """

        return mean(
            observation.magnitude_error
            for observation in self.observations
        )

    @property
    def flagged_observation_count(self) -> int:
        """
        Devuelve el número de observaciones con flags de catálogo.
        """

        return sum(
            observation.has_quality_flags
            for observation in self.observations
        )

    @property
    def unflagged_observation_count(self) -> int:
        """
        Devuelve el número de observaciones sin flags de catálogo.
        """

        return self.observation_count - self.flagged_observation_count

    @property
    def flagged_observation_rate(self) -> float:
        """
        Devuelve el porcentaje de observaciones con flags.

        Returns:
            Porcentaje comprendido entre 0 y 100.
        """

        return (
            self.flagged_observation_count
            / self.observation_count
        ) * 100.0

    @property
    def observations_by_time(
        self,
    ) -> tuple[LightCurveObservation, ...]:
        """
        Devuelve las observaciones ordenadas cronológicamente por MJD.

        La tupla almacenada originalmente no se modifica.
        """

        return tuple(
            sorted(
                self.observations,
                key=lambda observation: (
                    observation.modified_julian_date,
                    observation.exposure_id,
                ),
            )
        )

    @property
    def unflagged_observations(
        self,
    ) -> tuple[LightCurveObservation, ...]:
        """
        Devuelve únicamente las observaciones sin flags de catálogo.
        """

        return tuple(
            observation
            for observation in self.observations
            if observation.is_unflagged
        )

    @property
    def curve_key(self) -> str:
        """
        Devuelve una clave legible que identifica la curva.

        Ejemplo:

            458116300003161:g

        Esta propiedad es útil para logs y depuración, pero no sustituye las
        restricciones únicas de la base de datos.
        """

        return f"{self.ztf_object_id}:{self.band.value}"

    def has_minimum_observations(
        self,
        minimum_observations: int,
    ) -> bool:
        """
        Comprueba si la curva alcanza un número mínimo de observaciones.

        Args:
            minimum_observations:
                Número mínimo requerido.

        Returns:
            True cuando la curva contiene al menos esa cantidad.

        Raises:
            TypeError:
                Si el valor no es entero.

            ValueError:
                Si el valor es inferior a uno.
        """

        self._validate_required_integer(
            minimum_observations,
            field_name="minimum_observations",
            minimum=1,
        )

        return self.observation_count >= minimum_observations

    @staticmethod
    def _normalize_observations(
        observations: tuple[LightCurveObservation, ...],
    ) -> tuple[LightCurveObservation, ...]:
        """
        Valida y normaliza la colección de observaciones.

        Aunque el atributo está anotado como tuple, este método también
        acepta otras colecciones iterables y las convierte en una tupla
        inmutable.

        Returns:
            Tupla de observaciones validada.

        Raises:
            TypeError:
                Si el valor no es iterable o contiene elementos inválidos.

            ValueError:
                Si la colección está vacía.
        """

        if isinstance(observations, (str, bytes)):
            raise TypeError(
                "observations debe ser una colección de "
                "LightCurveObservation."
            )

        try:
            normalized_observations = tuple(observations)
        except TypeError as error:
            raise TypeError(
                "observations debe ser una colección iterable."
            ) from error

        if not normalized_observations:
            raise ValueError(
                "Una curva de luz debe contener al menos una observación."
            )

        for index, observation in enumerate(
            normalized_observations
        ):
            if not isinstance(
                observation,
                LightCurveObservation,
            ):
                raise TypeError(
                    "Todas las observaciones deben ser instancias de "
                    "LightCurveObservation. "
                    f"Elemento inválido en la posición {index}: "
                    f"{type(observation).__name__}."
                )

        return normalized_observations

    @classmethod
    def _validate_coordinate_pair(
        cls,
        *,
        right_ascension: float,
        declination: float,
        prefix: str,
    ) -> None:
        """
        Valida un par de coordenadas astronómicas.
        """

        cls._validate_required_float(
            right_ascension,
            field_name=f"{prefix}_right_ascension",
            minimum=0.0,
            maximum=360.0,
            maximum_inclusive=False,
        )

        cls._validate_required_float(
            declination,
            field_name=f"{prefix}_declination",
            minimum=-90.0,
            maximum=90.0,
        )

    @staticmethod
    def _validate_required_integer(
        value: int,
        *,
        field_name: str,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> None:
        """
        Valida un entero obligatorio.
        """

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{field_name} debe ser un número entero."
            )

        if minimum is not None and value < minimum:
            raise ValueError(
                f"{field_name} debe ser igual o superior a {minimum}. "
                f"Valor recibido: {value}."
            )

        if maximum is not None and value > maximum:
            raise ValueError(
                f"{field_name} debe ser igual o inferior a {maximum}. "
                f"Valor recibido: {value}."
            )

    @staticmethod
    def _validate_required_float(
        value: float,
        *,
        field_name: str,
        minimum: float | None = None,
        maximum: float | None = None,
        minimum_inclusive: bool = True,
        maximum_inclusive: bool = True,
    ) -> None:
        """
        Valida un número real obligatorio.
        """

        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(
                f"{field_name} debe ser un número real."
            )

        numeric_value = float(value)

        if not isfinite(numeric_value):
            raise ValueError(
                f"{field_name} debe contener un valor finito."
            )

        if minimum is not None:
            if minimum_inclusive and numeric_value < minimum:
                raise ValueError(
                    f"{field_name} debe ser igual o superior a "
                    f"{minimum}. Valor recibido: {numeric_value}."
                )

            if (
                not minimum_inclusive
                and numeric_value <= minimum
            ):
                raise ValueError(
                    f"{field_name} debe ser superior a {minimum}. "
                    f"Valor recibido: {numeric_value}."
                )

        if maximum is not None:
            if maximum_inclusive and numeric_value > maximum:
                raise ValueError(
                    f"{field_name} debe ser igual o inferior a "
                    f"{maximum}. Valor recibido: {numeric_value}."
                )

            if (
                not maximum_inclusive
                and numeric_value >= maximum
            ):
                raise ValueError(
                    f"{field_name} debe ser inferior a {maximum}. "
                    f"Valor recibido: {numeric_value}."
                )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        field_name: str,
    ) -> str:
        """
        Valida y normaliza un string obligatorio.
        """

        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} debe ser de tipo str."
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError(
                f"{field_name} no puede estar vacío."
            )

        return normalized_value