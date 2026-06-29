"""
Entidad de dominio que representa un objeto astronómico candidato.

Cada instancia de StarCandidate representa una fila del archivo
resultados.csv una vez que sus valores han sido transformados y validados.

Esta entidad no conoce:

- Cómo se lee el archivo CSV.
- Cómo se consulta una API.
- Cómo se guarda en la base de datos.
- Cómo se representa mediante SQLAlchemy.

Su responsabilidad es representar los datos de un candidato dentro del
dominio de la aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True, kw_only=True)
class StarCandidate:
    """
    Representa un objeto astronómico candidato pendiente de análisis.

    Attributes:
        alert_url:
            URL de la alerta astronómica original.

        observation_date:
            Fecha y hora asociadas a la detección o alerta.

        right_ascension:
            Ascensión recta de la fuente, expresada en grados.

        declination:
            Declinación de la fuente, expresada en grados.

        closest_simbad_target:
            Nombre del objeto más cercano encontrado en SIMBAD.
            Puede no existir si no se encontró ninguna coincidencia.

        object_class:
            Clasificación astronómica obtenida de SIMBAD.
            Puede no existir si el objeto no está clasificado.

        angular_distance:
            Distancia angular respecto al objeto más cercano de SIMBAD.
            Puede no existir si no se encontró una coincidencia.

        gaia_dr3_name:
            Identificador del objeto en Gaia Data Release 3.

        gaia_g_magnitude:
            Magnitud observada en la banda G de Gaia.

        gaia_bp_magnitude:
            Magnitud observada en la banda BP de Gaia.

        gaia_rp_magnitude:
            Magnitud observada en la banda RP de Gaia.

        parallax:
            Paralaje medida por Gaia.

        parallax_error:
            Incertidumbre asociada a la paralaje.

        is_in_white_dwarf_zone:
            Indica si el objeto se encuentra en la región asociada a
            enanas blancas.

        has_spectrum:
            Indica si existe un espectro disponible para el objeto.

        has_emission:
            Indica si se han detectado características de emisión.

        data_file_url:
            URL del archivo de datos asociado al candidato.
            Puede no existir.

        plot_url:
            URL de la gráfica generada para el candidato.
            Puede no existir.
    """

    alert_url: str
    observation_date: datetime

    right_ascension: float
    declination: float

    closest_simbad_target: str | None
    object_class: str | None
    angular_distance: float | None

    gaia_dr3_name: str
    gaia_g_magnitude: float
    gaia_bp_magnitude: float
    gaia_rp_magnitude: float
    parallax: float
    parallax_error: float

    is_in_white_dwarf_zone: bool
    has_spectrum: bool
    has_emission: bool

    data_file_url: str | None
    plot_url: str | None

    def __post_init__(self) -> None:
        """
        Valida las invariantes básicas de la entidad.

        Como la clase es una dataclass congelada, estas comprobaciones se
        realizan inmediatamente después de construir cada instancia.

        Raises:
            TypeError:
                Si alguno de los campos principales tiene un tipo incorrecto.

            ValueError:
                Si algún valor está vacío, fuera de rango o no es finito.
        """

        self._validate_required_strings()
        self._validate_coordinates()
        self._validate_measurements()
        self._validate_optional_values()
        self._validate_urls()

    @property
    def alert_id(self) -> str:
        """
        Obtiene el identificador del objeto a partir de la URL de alerta.

        Por ejemplo:

            https://alerce.online/object/ZTF17aaajocf

        produce:

            ZTF17aaajocf

        Returns:
            Identificador de la alerta.

        Raises:
            ValueError:
                Si la URL no contiene un identificador.
        """

        identifier = self.alert_url.rstrip("/").rsplit("/", maxsplit=1)[-1]

        if not identifier:
            raise ValueError(
                "No se pudo obtener el identificador desde alert_url."
            )

        return identifier

    @property
    def has_simbad_match(self) -> bool:
        """
        Indica si el candidato tiene una coincidencia válida en SIMBAD.

        Returns:
            True cuando existe un objeto de SIMBAD y una distancia angular.
        """

        return (
            self.closest_simbad_target is not None
            and self.angular_distance is not None
        )

    @property
    def has_generated_resources(self) -> bool:
        """
        Indica si existen tanto el archivo de datos como la gráfica.

        Returns:
            True cuando ambas URLs están disponibles.
        """

        return (
            self.data_file_url is not None
            and self.plot_url is not None
        )

    def _validate_required_strings(self) -> None:
        """
        Valida los textos obligatorios de la entidad.
        """

        required_strings = {
            "alert_url": self.alert_url,
            "gaia_dr3_name": self.gaia_dr3_name,
        }

        for field_name, value in required_strings.items():
            if not isinstance(value, str):
                raise TypeError(
                    f"{field_name} debe ser de tipo str."
                )

            if not value.strip():
                raise ValueError(
                    f"{field_name} no puede estar vacío."
                )

    def _validate_coordinates(self) -> None:
        """
        Valida las coordenadas ecuatoriales.

        La ascensión recta expresada en grados debe estar en el intervalo
        [0, 360), mientras que la declinación debe encontrarse entre
        -90 y 90 grados.
        """

        self._validate_finite_number(
            field_name="right_ascension",
            value=self.right_ascension,
        )
        self._validate_finite_number(
            field_name="declination",
            value=self.declination,
        )

        if not 0.0 <= self.right_ascension < 360.0:
            raise ValueError(
                "right_ascension debe estar en el intervalo [0, 360)."
            )

        if not -90.0 <= self.declination <= 90.0:
            raise ValueError(
                "declination debe estar en el intervalo [-90, 90]."
            )

    def _validate_measurements(self) -> None:
        """
        Valida las medidas numéricas obligatorias.

        No se restringen las magnitudes ni la paralaje a valores positivos,
        porque astronómicamente pueden existir magnitudes negativas y
        paralajes medidas con valores negativos.
        """

        measurements = {
            "gaia_g_magnitude": self.gaia_g_magnitude,
            "gaia_bp_magnitude": self.gaia_bp_magnitude,
            "gaia_rp_magnitude": self.gaia_rp_magnitude,
            "parallax": self.parallax,
            "parallax_error": self.parallax_error,
        }

        for field_name, value in measurements.items():
            self._validate_finite_number(
                field_name=field_name,
                value=value,
            )

        if self.parallax_error < 0:
            raise ValueError(
                "parallax_error no puede ser negativa."
            )

    def _validate_optional_values(self) -> None:
        """
        Valida los campos opcionales y booleanos.
        """

        optional_strings = {
            "closest_simbad_target": self.closest_simbad_target,
            "object_class": self.object_class,
        }

        for field_name, value in optional_strings.items():
            if value is not None and not isinstance(value, str):
                raise TypeError(
                    f"{field_name} debe ser str o None."
                )

            if isinstance(value, str) and not value.strip():
                raise ValueError(
                    f"{field_name} no puede ser una cadena vacía. "
                    "Utiliza None cuando el valor no exista."
                )

        if self.angular_distance is not None:
            self._validate_finite_number(
                field_name="angular_distance",
                value=self.angular_distance,
            )

            if self.angular_distance < 0:
                raise ValueError(
                    "angular_distance no puede ser negativa."
                )

        boolean_fields = {
            "is_in_white_dwarf_zone": self.is_in_white_dwarf_zone,
            "has_spectrum": self.has_spectrum,
            "has_emission": self.has_emission,
        }

        for field_name, value in boolean_fields.items():
            if not isinstance(value, bool):
                raise TypeError(
                    f"{field_name} debe ser de tipo bool."
                )

    def _validate_urls(self) -> None:
        """
        Valida las URLs obligatorias y opcionales.
        """

        self._validate_url(
            field_name="alert_url",
            value=self.alert_url,
            required=True,
        )

        self._validate_url(
            field_name="data_file_url",
            value=self.data_file_url,
            required=False,
        )

        self._validate_url(
            field_name="plot_url",
            value=self.plot_url,
            required=False,
        )

    @staticmethod
    def _validate_finite_number(
        *,
        field_name: str,
        value: float,
    ) -> None:
        """
        Comprueba que un valor sea numérico y finito.

        Args:
            field_name:
                Nombre del campo que se está validando.

            value:
                Valor que debe comprobarse.

        Raises:
            TypeError:
                Si el valor no es un número.

            ValueError:
                Si el valor es infinito o NaN.
        """

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"{field_name} debe ser un valor numérico."
            )

        if not isfinite(value):
            raise ValueError(
                f"{field_name} debe ser un número finito."
            )

    @staticmethod
    def _validate_url(
        *,
        field_name: str,
        value: str | None,
        required: bool,
    ) -> None:
        """
        Comprueba que una URL tenga una estructura válida.

        Args:
            field_name:
                Nombre del campo.

            value:
                URL que debe validarse.

            required:
                Indica si el campo es obligatorio.

        Raises:
            TypeError:
                Si el valor no es un string.

            ValueError:
                Si la URL está vacía o no tiene una estructura válida.
        """

        if value is None:
            if required:
                raise ValueError(
                    f"{field_name} es obligatorio."
                )

            return

        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} debe ser str o None."
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError(
                f"{field_name} no puede estar vacío."
            )

        parsed_url = urlparse(normalized_value)

        if parsed_url.scheme not in {"http", "https"}:
            raise ValueError(
                f"{field_name} debe utilizar HTTP o HTTPS."
            )

        if not parsed_url.netloc:
            raise ValueError(
                f"{field_name} debe contener un dominio válido."
            )