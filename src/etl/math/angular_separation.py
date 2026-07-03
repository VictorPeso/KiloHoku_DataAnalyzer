"""
Servicios astronómicos para calcular separaciones angulares.

Este módulo proporciona funciones independientes de IRSA y de la base de
datos para calcular la distancia angular entre dos posiciones celestes.

Las posiciones se expresan mediante:

- Ascensión recta, en grados.
- Declinación, en grados.

La distancia resultante puede obtenerse en radianes, grados o segundos de
arco.
"""

from __future__ import annotations

import math


RADIANS_TO_DEGREES = 180.0 / math.pi
RADIANS_TO_ARCSECONDS = 3600.0 * RADIANS_TO_DEGREES


def angular_separation_radians(
    first_right_ascension_degrees: float,
    first_declination_degrees: float,
    second_right_ascension_degrees: float,
    second_declination_degrees: float,
) -> float:
    """
    Calcula la separación angular entre dos posiciones celestes.

    Se utiliza la fórmula del haversine esférico, que ofrece buena estabilidad
    numérica para separaciones angulares pequeñas.

    Args:
        first_right_ascension_degrees:
            Ascensión recta de la primera posición, en grados.

        first_declination_degrees:
            Declinación de la primera posición, en grados.

        second_right_ascension_degrees:
            Ascensión recta de la segunda posición, en grados.

        second_declination_degrees:
            Declinación de la segunda posición, en grados.

    Returns:
        Separación angular expresada en radianes.

    Raises:
        TypeError:
            Si alguna coordenada no es un número real.

        ValueError:
            Si alguna coordenada no es finita o está fuera de su rango.
    """

    first_right_ascension = _validate_right_ascension(
        first_right_ascension_degrees,
        field_name="first_right_ascension_degrees",
    )
    first_declination = _validate_declination(
        first_declination_degrees,
        field_name="first_declination_degrees",
    )
    second_right_ascension = _validate_right_ascension(
        second_right_ascension_degrees,
        field_name="second_right_ascension_degrees",
    )
    second_declination = _validate_declination(
        second_declination_degrees,
        field_name="second_declination_degrees",
    )

    first_ra_radians = math.radians(first_right_ascension)
    first_dec_radians = math.radians(first_declination)

    second_ra_radians = math.radians(second_right_ascension)
    second_dec_radians = math.radians(second_declination)

    delta_right_ascension = _normalize_radian_difference(
        second_ra_radians - first_ra_radians
    )
    delta_declination = (
        second_dec_radians - first_dec_radians
    )

    haversine_value = (
        math.sin(delta_declination / 2.0) ** 2
        + math.cos(first_dec_radians)
        * math.cos(second_dec_radians)
        * math.sin(delta_right_ascension / 2.0) ** 2
    )

    # Los errores de redondeo pueden generar valores ligeramente inferiores
    # a 0 o superiores a 1, lo que produciría un error en asin().
    bounded_haversine = min(
        1.0,
        max(0.0, haversine_value),
    )

    return 2.0 * math.asin(
        math.sqrt(bounded_haversine)
    )


def angular_separation_degrees(
    first_right_ascension_degrees: float,
    first_declination_degrees: float,
    second_right_ascension_degrees: float,
    second_declination_degrees: float,
) -> float:
    """
    Calcula la separación angular en grados.

    Args:
        first_right_ascension_degrees:
            Ascensión recta de la primera posición.

        first_declination_degrees:
            Declinación de la primera posición.

        second_right_ascension_degrees:
            Ascensión recta de la segunda posición.

        second_declination_degrees:
            Declinación de la segunda posición.

    Returns:
        Separación angular expresada en grados.
    """

    separation_radians = angular_separation_radians(
        first_right_ascension_degrees,
        first_declination_degrees,
        second_right_ascension_degrees,
        second_declination_degrees,
    )

    return separation_radians * RADIANS_TO_DEGREES


def angular_separation_arcsec(
    first_right_ascension_degrees: float,
    first_declination_degrees: float,
    second_right_ascension_degrees: float,
    second_declination_degrees: float,
) -> float:
    """
    Calcula la separación angular en segundos de arco.

    Esta será la función principal para seleccionar la fuente ZTF más próxima
    a las coordenadas del candidato estudiado.

    Args:
        first_right_ascension_degrees:
            Ascensión recta de la primera posición.

        first_declination_degrees:
            Declinación de la primera posición.

        second_right_ascension_degrees:
            Ascensión recta de la segunda posición.

        second_declination_degrees:
            Declinación de la segunda posición.

    Returns:
        Separación angular expresada en segundos de arco.
    """

    separation_radians = angular_separation_radians(
        first_right_ascension_degrees,
        first_declination_degrees,
        second_right_ascension_degrees,
        second_declination_degrees,
    )

    return separation_radians * RADIANS_TO_ARCSECONDS


def _validate_right_ascension(
    value: float,
    *,
    field_name: str,
) -> float:
    """
    Valida una ascensión recta expresada en grados.

    El rango admitido es:

        0 <= RA < 360

    Returns:
        Valor normalizado como float.
    """

    normalized_value = _validate_real(
        value,
        field_name=field_name,
    )

    if not 0.0 <= normalized_value < 360.0:
        raise ValueError(
            f"{field_name} debe estar comprendido en el rango "
            f"[0, 360). Valor recibido: {normalized_value}."
        )

    return normalized_value


def _validate_declination(
    value: float,
    *,
    field_name: str,
) -> float:
    """
    Valida una declinación expresada en grados.

    El rango admitido es:

        -90 <= Dec <= 90

    Returns:
        Valor normalizado como float.
    """

    normalized_value = _validate_real(
        value,
        field_name=field_name,
    )

    if not -90.0 <= normalized_value <= 90.0:
        raise ValueError(
            f"{field_name} debe estar comprendido en el rango "
            f"[-90, 90]. Valor recibido: {normalized_value}."
        )

    return normalized_value


def _validate_real(
    value: float,
    *,
    field_name: str,
) -> float:
    """
    Valida y normaliza un número real finito.

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

    return normalized_value


def _normalize_radian_difference(
    difference_radians: float,
) -> float:
    """
    Normaliza una diferencia angular al intervalo [-pi, pi].

    Esto permite calcular correctamente distancias próximas al límite entre
    0 y 360 grados.

    Por ejemplo, la diferencia entre RA=359.9° y RA=0.1° debe considerarse
    aproximadamente 0.2°, no 359.8°.
    """

    return (
        difference_radians + math.pi
    ) % (2.0 * math.pi) - math.pi