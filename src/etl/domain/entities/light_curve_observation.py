"""
Entidad de dominio que representa una observación de una curva de luz.

Cada instancia corresponde a una fila del VOTable devuelto por la API
de curvas de luz de ZTF de NASA/IPAC.

La observación contiene:

- El instante de la observación.
- La magnitud medida y su incertidumbre.
- Información sobre la exposición.
- Coordenadas de la detección.
- Indicadores de calidad fotométrica.
- Información instrumental y de calibración.

El identificador del objeto ZTF y la banda fotométrica no se almacenan en
esta entidad porque pertenecen a la curva de luz que agrupa las observaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True, kw_only=True)
class LightCurveObservation:
    """
    Punto individual de una curva de luz ZTF.

    Attributes:
        exposure_id:
            Identificador de la exposición ZTF, correspondiente a ``expid``.

        heliocentric_julian_date:
            Fecha juliana heliocéntrica del punto medio de la exposición,
            correspondiente a ``hjd``.

        modified_julian_date:
            Fecha juliana modificada del inicio de la exposición,
            correspondiente a ``mjd``.

        magnitude:
            Magnitud fotométrica medida.

        magnitude_error:
            Incertidumbre asociada a la magnitud.

        catalog_flags:
            Indicadores de calidad del catálogo ZTF.

        right_ascension:
            Ascensión recta de la detección en grados.

        declination:
            Declinación de la detección en grados.

        chi:
            Parámetro chi-cuadrado del ajuste PSF.

        sharpness:
            Parámetro de nitidez del ajuste PSF.

        file_fraction_day:
            Marca temporal del archivo de exposición en el formato numérico
            proporcionado por ZTF.

        field_id:
            Identificador del campo ZTF.

        ccd_id:
            Identificador del CCD, normalmente comprendido entre 1 y 16.

        quadrant_id:
            Identificador del cuadrante del CCD, normalmente entre 1 y 4.

        limiting_magnitude:
            Magnitud límite aproximada a cinco sigma.

        magnitude_zero_point:
            Punto cero de la calibración fotométrica.

        magnitude_zero_point_rms:
            Desviación RMS del punto cero fotométrico.

        color_coefficient:
            Coeficiente de color de la calibración.

        color_coefficient_error:
            Incertidumbre del coeficiente de color.

        exposure_time:
            Duración de la exposición en segundos.

        airmass:
            Masa de aire durante la observación.

        program_id:
            Identificador del programa de observación ZTF.
    """

    exposure_id: int

    heliocentric_julian_date: float
    modified_julian_date: float

    magnitude: float
    magnitude_error: float

    catalog_flags: int

    right_ascension: float
    declination: float

    chi: float | None = None
    sharpness: float | None = None

    file_fraction_day: int | None = None
    field_id: int | None = None
    ccd_id: int | None = None
    quadrant_id: int | None = None

    limiting_magnitude: float | None = None
    magnitude_zero_point: float | None = None
    magnitude_zero_point_rms: float | None = None

    color_coefficient: float | None = None
    color_coefficient_error: float | None = None

    exposure_time: float | None = None
    airmass: float | None = None
    program_id: int | None = None

    def __post_init__(self) -> None:
        """
        Valida los datos de la observación después de crearla.

        Raises:
            TypeError:
                Si alguno de los valores no tiene el tipo esperado.

            ValueError:
                Si algún valor está fuera de un rango permitido o no es
                numéricamente válido.
        """

        self._validate_required_integer(
            self.exposure_id,
            field_name="exposure_id",
            minimum=0,
        )

        self._validate_required_float(
            self.heliocentric_julian_date,
            field_name="heliocentric_julian_date",
        )

        self._validate_required_float(
            self.modified_julian_date,
            field_name="modified_julian_date",
        )

        self._validate_required_float(
            self.magnitude,
            field_name="magnitude",
        )

        self._validate_required_float(
            self.magnitude_error,
            field_name="magnitude_error",
            minimum=0.0,
        )

        self._validate_required_integer(
            self.catalog_flags,
            field_name="catalog_flags",
            minimum=0,
        )

        self._validate_required_float(
            self.right_ascension,
            field_name="right_ascension",
            minimum=0.0,
            maximum=360.0,
            maximum_inclusive=False,
        )

        self._validate_required_float(
            self.declination,
            field_name="declination",
            minimum=-90.0,
            maximum=90.0,
        )

        self._validate_optional_float(
            self.chi,
            field_name="chi",
        )

        self._validate_optional_float(
            self.sharpness,
            field_name="sharpness",
        )

        self._validate_optional_integer(
            self.file_fraction_day,
            field_name="file_fraction_day",
            minimum=0,
        )

        self._validate_optional_integer(
            self.field_id,
            field_name="field_id",
            minimum=0,
        )

        self._validate_optional_integer(
            self.ccd_id,
            field_name="ccd_id",
            minimum=1,
            maximum=16,
        )

        self._validate_optional_integer(
            self.quadrant_id,
            field_name="quadrant_id",
            minimum=1,
            maximum=4,
        )

        self._validate_optional_float(
            self.limiting_magnitude,
            field_name="limiting_magnitude",
        )

        self._validate_optional_float(
            self.magnitude_zero_point,
            field_name="magnitude_zero_point",
        )

        self._validate_optional_float(
            self.magnitude_zero_point_rms,
            field_name="magnitude_zero_point_rms",
            minimum=0.0,
        )

        self._validate_optional_float(
            self.color_coefficient,
            field_name="color_coefficient",
        )

        self._validate_optional_float(
            self.color_coefficient_error,
            field_name="color_coefficient_error",
            minimum=0.0,
        )

        self._validate_optional_float(
            self.exposure_time,
            field_name="exposure_time",
            minimum=0.0,
        )

        self._validate_optional_float(
            self.airmass,
            field_name="airmass",
            minimum=0.0,
        )

        self._validate_optional_integer(
            self.program_id,
            field_name="program_id",
            minimum=0,
        )

    @property
    def has_quality_flags(self) -> bool:
        """
        Indica si ZTF ha asociado algún indicador de calidad a la observación.

        Una observación con ``catalog_flags == 0`` no tiene flags activos.
        Que el valor sea distinto de cero no implica necesariamente que deba
        descartarse; la interpretación se realizará posteriormente durante
        la validación y limpieza de la curva.
        """

        return self.catalog_flags != 0

    @property
    def is_unflagged(self) -> bool:
        """
        Indica si la observación no contiene flags de catálogo.
        """

        return self.catalog_flags == 0

    @property
    def signal_to_noise_proxy(self) -> float | None:
        """
        Calcula una aproximación de la relación señal-ruido desde el error.

        Para magnitudes astronómicas puede utilizarse la aproximación:

            SNR ≈ 1.0857 / error_de_magnitud

        Returns:
            Aproximación de la relación señal-ruido, o None cuando el error
            de magnitud es cero.
        """

        if self.magnitude_error == 0:
            return None

        return 1.0857 / self.magnitude_error

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

        LightCurveObservation._validate_numeric_range(
            value,
            field_name=field_name,
            minimum=minimum,
            maximum=maximum,
        )

    @staticmethod
    def _validate_optional_integer(
        value: int | None,
        *,
        field_name: str,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> None:
        """
        Valida un entero opcional.
        """

        if value is None:
            return

        LightCurveObservation._validate_required_integer(
            value,
            field_name=field_name,
            minimum=minimum,
            maximum=maximum,
        )

    @staticmethod
    def _validate_required_float(
        value: float,
        *,
        field_name: str,
        minimum: float | None = None,
        maximum: float | None = None,
        maximum_inclusive: bool = True,
    ) -> None:
        """
        Valida un número real obligatorio.
        """

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"{field_name} debe ser un número real."
            )

        numeric_value = float(value)

        if not isfinite(numeric_value):
            raise ValueError(
                f"{field_name} debe contener un valor finito."
            )

        LightCurveObservation._validate_numeric_range(
            numeric_value,
            field_name=field_name,
            minimum=minimum,
            maximum=maximum,
            maximum_inclusive=maximum_inclusive,
        )

    @staticmethod
    def _validate_optional_float(
        value: float | None,
        *,
        field_name: str,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> None:
        """
        Valida un número real opcional.
        """

        if value is None:
            return

        LightCurveObservation._validate_required_float(
            value,
            field_name=field_name,
            minimum=minimum,
            maximum=maximum,
        )

    @staticmethod
    def _validate_numeric_range(
        value: int | float,
        *,
        field_name: str,
        minimum: int | float | None = None,
        maximum: int | float | None = None,
        maximum_inclusive: bool = True,
    ) -> None:
        """
        Comprueba que un valor se encuentre dentro de un rango.
        """

        if minimum is not None and value < minimum:
            raise ValueError(
                f"{field_name} debe ser igual o superior a {minimum}. "
                f"Valor recibido: {value}."
            )

        if maximum is None:
            return

        if maximum_inclusive and value > maximum:
            raise ValueError(
                f"{field_name} debe ser igual o inferior a {maximum}. "
                f"Valor recibido: {value}."
            )

        if not maximum_inclusive and value >= maximum:
            raise ValueError(
                f"{field_name} debe ser inferior a {maximum}. "
                f"Valor recibido: {value}."
            )