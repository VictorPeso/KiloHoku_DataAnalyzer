"""
Entidad de dominio para una fuente candidata encontrada en IRSA.

Una consulta posicional a la API de curvas de luz ZTF puede devolver varias
fuentes dentro del radio de búsqueda. Cada fuente se identifica mediante la
combinación:

    ztf_object_id + banda fotométrica

Esta entidad representa una posible correspondencia entre un candidato
astronómico del proyecto y un objeto ZTF encontrado en IRSA.

No representa todavía una curva de luz completa. Contiene únicamente los
datos necesarios para evaluar y seleccionar la fuente más próxima a las
coordenadas estudiadas.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from etl.domain.value_objects import PhotometricBand


@dataclass(frozen=True, slots=True, kw_only=True)
class IrsaLightCurveSource:
    """
    Fuente ZTF candidata encontrada mediante una consulta posicional.

    Attributes:
        ztf_object_id:
            Identificador ``oid`` utilizado por ZTF/IRSA.

        band:
            Banda fotométrica de la fuente: g, r o i.

        right_ascension:
            Ascensión recta representativa de la fuente, en grados.

        declination:
            Declinación representativa de la fuente, en grados.

        observation_count:
            Número total de observaciones encontradas para la combinación
            de objeto y banda.

        clean_observation_count:
            Número de observaciones sin flags de catálogo, es decir,
            observaciones con ``catflags == 0``.

        angular_distance_arcsec:
            Separación angular entre la fuente y las coordenadas del
            candidato estudiado, expresada en segundos de arco.
    """

    ztf_object_id: int
    band: PhotometricBand

    right_ascension: float
    declination: float

    observation_count: int
    clean_observation_count: int

    angular_distance_arcsec: float

    def __post_init__(self) -> None:
        """
        Normaliza y valida los valores de la fuente.

        Raises:
            TypeError:
                Si alguno de los campos no tiene el tipo esperado.

            ValueError:
                Si alguno de los valores está fuera de su rango permitido.
        """

        normalized_band = PhotometricBand.from_value(self.band)

        object.__setattr__(
            self,
            "band",
            normalized_band,
        )

        normalized_right_ascension = self._validate_real(
            self.right_ascension,
            field_name="right_ascension",
            minimum=0.0,
            maximum=360.0,
            maximum_inclusive=False,
        )

        normalized_declination = self._validate_real(
            self.declination,
            field_name="declination",
            minimum=-90.0,
            maximum=90.0,
        )

        normalized_angular_distance = self._validate_real(
            self.angular_distance_arcsec,
            field_name="angular_distance_arcsec",
            minimum=0.0,
        )

        self._validate_positive_integer(
            self.ztf_object_id,
            field_name="ztf_object_id",
        )

        self._validate_non_negative_integer(
            self.observation_count,
            field_name="observation_count",
        )

        self._validate_non_negative_integer(
            self.clean_observation_count,
            field_name="clean_observation_count",
        )

        if self.observation_count == 0:
            raise ValueError(
                "observation_count debe ser mayor que cero para representar "
                "una fuente encontrada en IRSA."
            )

        if self.clean_observation_count > self.observation_count:
            raise ValueError(
                "clean_observation_count no puede ser mayor que "
                "observation_count. "
                f"Valores recibidos: clean={self.clean_observation_count}, "
                f"total={self.observation_count}."
            )

        object.__setattr__(
            self,
            "right_ascension",
            normalized_right_ascension,
        )

        object.__setattr__(
            self,
            "declination",
            normalized_declination,
        )

        object.__setattr__(
            self,
            "angular_distance_arcsec",
            normalized_angular_distance,
        )

    @property
    def source_key(self) -> str:
        """
        Devuelve una clave legible que identifica la fuente y su banda.

        Ejemplo:

            791111200002971:g
        """

        return f"{self.ztf_object_id}:{self.band.value}"

    @property
    def filter_code(self) -> str:
        """
        Devuelve el código de filtro utilizado en las respuestas de ZTF.

        Ejemplos:

            PhotometricBand.G -> "zg"
            PhotometricBand.R -> "zr"
            PhotometricBand.I -> "zi"
        """

        return f"z{self.band.value}"

    @property
    def flagged_observation_count(self) -> int:
        """
        Devuelve el número de observaciones que contienen algún catflag.
        """

        return (
            self.observation_count
            - self.clean_observation_count
        )

    @property
    def clean_observation_fraction(self) -> float:
        """
        Devuelve la proporción de observaciones sin flags.

        El resultado está comprendido entre 0 y 1.
        """

        return (
            self.clean_observation_count
            / self.observation_count
        )

    @property
    def clean_observation_percentage(self) -> float:
        """
        Devuelve el porcentaje de observaciones sin flags.
        """

        return self.clean_observation_fraction * 100.0

    @property
    def has_clean_observations(self) -> bool:
        """
        Indica si la fuente contiene al menos una observación limpia.
        """

        return self.clean_observation_count > 0

    def meets_minimum_observations(
        self,
        minimum_observations: int,
        *,
        use_clean_observations: bool = True,
    ) -> bool:
        """
        Comprueba si la fuente alcanza un mínimo de observaciones.

        Args:
            minimum_observations:
                Número mínimo de observaciones requerido.

            use_clean_observations:
                Si es True, utiliza únicamente las observaciones con
                ``catflags == 0``. Si es False, utiliza el número total de
                observaciones.

        Returns:
            True si la fuente alcanza el mínimo indicado.

        Raises:
            TypeError:
                Si los argumentos no tienen los tipos esperados.

            ValueError:
                Si el mínimo es menor que uno.
        """

        self._validate_positive_integer(
            minimum_observations,
            field_name="minimum_observations",
        )

        if not isinstance(use_clean_observations, bool):
            raise TypeError(
                "use_clean_observations debe ser de tipo bool."
            )

        count = (
            self.clean_observation_count
            if use_clean_observations
            else self.observation_count
        )

        return count >= minimum_observations

    @staticmethod
    def _validate_real(
        value: float,
        *,
        field_name: str,
        minimum: float | None = None,
        maximum: float | None = None,
        minimum_inclusive: bool = True,
        maximum_inclusive: bool = True,
    ) -> float:
        """
        Valida y normaliza un número real.

        Returns:
            Valor convertido a float.
        """

        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(
                f"{field_name} debe ser un número real."
            )

        normalized_value = float(value)

        if not math.isfinite(normalized_value):
            raise ValueError(
                f"{field_name} debe ser un número finito."
            )

        if minimum is not None:
            if (
                minimum_inclusive
                and normalized_value < minimum
            ):
                raise ValueError(
                    f"{field_name} debe ser igual o superior a "
                    f"{minimum}."
                )

            if (
                not minimum_inclusive
                and normalized_value <= minimum
            ):
                raise ValueError(
                    f"{field_name} debe ser superior a {minimum}."
                )

        if maximum is not None:
            if (
                maximum_inclusive
                and normalized_value > maximum
            ):
                raise ValueError(
                    f"{field_name} debe ser igual o inferior a "
                    f"{maximum}."
                )

            if (
                not maximum_inclusive
                and normalized_value >= maximum
            ):
                raise ValueError(
                    f"{field_name} debe ser inferior a {maximum}."
                )

        return normalized_value

    @staticmethod
    def _validate_positive_integer(
        value: int,
        *,
        field_name: str,
    ) -> None:
        """
        Valida que un valor sea un entero positivo.
        """

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{field_name} debe ser un número entero."
            )

        if value <= 0:
            raise ValueError(
                f"{field_name} debe ser mayor que cero."
            )

    @staticmethod
    def _validate_non_negative_integer(
        value: int,
        *,
        field_name: str,
    ) -> None:
        """
        Valida que un valor sea un entero no negativo.
        """

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{field_name} debe ser un número entero."
            )

        if value < 0:
            raise ValueError(
                f"{field_name} no puede ser negativo."
            )