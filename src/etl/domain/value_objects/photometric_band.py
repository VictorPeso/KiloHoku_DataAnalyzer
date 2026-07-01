"""
Bandas fotométricas utilizadas por ZTF.

Este módulo define las bandas admitidas durante la descarga y el
procesamiento de curvas de luz.

La API de IRSA utiliza los valores:

    g
    r
    i

Mientras que los VOTable devueltos por ZTF suelen utilizar códigos:

    zg
    zr
    zi

PhotometricBand centraliza ambas representaciones para evitar utilizar
strings sin validar en el resto de la aplicación.
"""

from __future__ import annotations

from enum import StrEnum


class PhotometricBand(StrEnum):
    """
    Banda fotométrica de una curva de luz ZTF.

    Values:
        G:
            Banda verde de ZTF.

        R:
            Banda roja de ZTF.

        I:
            Banda infrarroja cercana de ZTF.
    """

    G = "g"
    R = "r"
    I = "i"

    @property
    def ztf_filter_code(self) -> str:
        """
        Devuelve el código de filtro utilizado dentro de los VOTable ZTF.

        Returns:
            Código ``zg``, ``zr`` o ``zi``.
        """

        return f"z{self.value}"

    @property
    def display_name(self) -> str:
        """
        Devuelve un nombre legible para mostrar en logs o interfaces.
        """

        names = {
            PhotometricBand.G: "ZTF g",
            PhotometricBand.R: "ZTF r",
            PhotometricBand.I: "ZTF i",
        }

        return names[self]

    @classmethod
    def from_value(
        cls,
        value: str | PhotometricBand,
    ) -> PhotometricBand:
        """
        Convierte un valor de banda en PhotometricBand.

        Admite tanto los valores empleados por la API de IRSA como los
        códigos encontrados en los VOTable.

        Valores admitidos:

            g, r, i
            zg, zr, zi

        La conversión ignora espacios exteriores y diferencias entre
        mayúsculas y minúsculas.

        Args:
            value:
                Banda que debe convertirse.

        Returns:
            Banda fotométrica normalizada.

        Raises:
            TypeError:
                Si el valor no es str ni PhotometricBand.

            ValueError:
                Si el valor no representa una banda admitida.
        """

        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise TypeError(
                "La banda fotométrica debe ser un string o "
                "una instancia de PhotometricBand."
            )

        normalized_value = value.strip().lower()

        if normalized_value.startswith("z"):
            normalized_value = normalized_value[1:]

        try:
            return cls(normalized_value)
        except ValueError as error:
            valid_values = ", ".join(
                band.value
                for band in cls
            )

            raise ValueError(
                "Banda fotométrica no válida. "
                f"Valor recibido: {value!r}. "
                f"Valores admitidos: {valid_values}."
            ) from error

    @classmethod
    def from_ztf_filter_code(
        cls,
        filter_code: str,
    ) -> PhotometricBand:
        """
        Convierte específicamente un código de filtro ZTF.

        Args:
            filter_code:
                Código ``zg``, ``zr`` o ``zi``.

        Returns:
            Banda fotométrica correspondiente.

        Raises:
            TypeError:
                Si el código no es un string.

            ValueError:
                Si no utiliza el formato esperado o la banda no existe.
        """

        if not isinstance(filter_code, str):
            raise TypeError(
                "filter_code debe ser de tipo str."
            )

        normalized_code = filter_code.strip().lower()

        valid_codes = {
            band.ztf_filter_code: band
            for band in cls
        }

        try:
            return valid_codes[normalized_code]
        except KeyError as error:
            raise ValueError(
                "Código de filtro ZTF no válido. "
                f"Valor recibido: {filter_code!r}. "
                "Valores admitidos: zg, zr, zi."
            ) from error

    @classmethod
    def default_download_bands(
        cls,
    ) -> tuple[PhotometricBand, ...]:
        """
        Devuelve las bandas que se descargarán inicialmente.

        Las primeras pruebas se realizarán con g y r porque son las bandas
        con mayor disponibilidad de observaciones. La banda i podrá añadirse
        posteriormente mediante configuración.

        Returns:
            Tupla inmutable con las bandas g y r.
        """

        return (
            cls.G,
            cls.R,
        )