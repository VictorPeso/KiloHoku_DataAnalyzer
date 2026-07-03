"""
Cliente HTTP para la API de curvas de luz ZTF de NASA/IPAC IRSA.

Este cliente únicamente se ocupa de:

- Construir los parámetros de la consulta.
- Realizar la petición HTTP.
- Validar la respuesta básica.
- Devolver el contenido VOTable en bytes.

No interpreta el XML ni accede a PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import math

from etl.domain.value_objects import PhotometricBand
from etl.config import settings
from etl.logger import get_logger

from etl.extractors.exceptions import (
    IrsaConnectionError,
    IrsaResponseError,
)

logger = get_logger(__name__)


IRSA_ZTF_LIGHT_CURVE_URL = (
    "https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class IrsaLightCurveQuery:
    """
    Parámetros de una consulta de curvas de luz.

    Attributes:
        right_ascension:
            Ascensión recta del centro de búsqueda, en grados.

        declination:
            Declinación del centro de búsqueda, en grados.

        radius_degrees:
            Radio de búsqueda en grados.

        band:
            Banda fotométrica g, r o i.

        minimum_observations:
            Número mínimo de observaciones requerido para cada objeto.

        bad_catalog_flags_mask:
            Máscara opcional para excluir observaciones con determinados
            catflags.
    """

    right_ascension: float
    declination: float
    radius_degrees: float
    band: PhotometricBand
    minimum_observations: int = (
        settings.irsa_minimum_observations
    )
    bad_catalog_flags_mask: int | None = (
        settings.irsa_bad_catalog_flags_mask
    )

    def __post_init__(self) -> None:
        normalized_band = PhotometricBand.from_value(self.band)

        object.__setattr__(
            self,
            "band",
            normalized_band,
        )

        self._validate_real(
            self.right_ascension,
            field_name="right_ascension",
            minimum=0.0,
            maximum=360.0,
            maximum_inclusive=False,
        )

        self._validate_real(
            self.declination,
            field_name="declination",
            minimum=-90.0,
            maximum=90.0,
        )

        self._validate_real(
            self.radius_degrees,
            field_name="radius_degrees",
            minimum=0.0,
            minimum_inclusive=False,
        )

        if (
            isinstance(self.minimum_observations, bool)
            or not isinstance(self.minimum_observations, int)
        ):
            raise TypeError(
                "minimum_observations debe ser un número entero."
            )

        if self.minimum_observations < 1:
            raise ValueError(
                "minimum_observations debe ser mayor que cero."
            )

        if self.bad_catalog_flags_mask is not None:
            if (
                isinstance(self.bad_catalog_flags_mask, bool)
                or not isinstance(self.bad_catalog_flags_mask, int)
            ):
                raise TypeError(
                    "bad_catalog_flags_mask debe ser entero o None."
                )

            if self.bad_catalog_flags_mask < 0:
                raise ValueError(
                    "bad_catalog_flags_mask no puede ser negativo."
                )

    def to_query_parameters(self) -> dict[str, str]:
        """
        Convierte la consulta en parámetros HTTP admitidos por IRSA.
        """

        parameters = {
            "POS": (
                f"CIRCLE "
                f"{self.right_ascension:.10f} "
                f"{self.declination:.10f} "
                f"{self.radius_degrees:.10f}"
            ),
            "BANDNAME": self.band.value,
            "NOBS_MIN": str(self.minimum_observations),
            "FORMAT": "votable",
        }

        if self.bad_catalog_flags_mask is not None:
            parameters["BAD_CATFLAGS_MASK"] = str(
                self.bad_catalog_flags_mask
            )

        return parameters

    @staticmethod
    def _validate_real(
        value: float,
        *,
        field_name: str,
        minimum: float | None = None,
        maximum: float | None = None,
        minimum_inclusive: bool = True,
        maximum_inclusive: bool = True,
    ) -> None:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(
                f"{field_name} debe ser un número real."
            )

        numeric_value = float(value)

        if not math.isfinite(numeric_value):
            raise ValueError(
                f"{field_name} debe ser finito."
            )

        if minimum is not None:
            if minimum_inclusive and numeric_value < minimum:
                raise ValueError(
                    f"{field_name} debe ser igual o superior a {minimum}."
                )

            if (
                not minimum_inclusive
                and numeric_value <= minimum
            ):
                raise ValueError(
                    f"{field_name} debe ser superior a {minimum}."
                )

        if maximum is not None:
            if maximum_inclusive and numeric_value > maximum:
                raise ValueError(
                    f"{field_name} debe ser igual o inferior a {maximum}."
                )

            if (
                not maximum_inclusive
                and numeric_value >= maximum
            ):
                raise ValueError(
                    f"{field_name} debe ser inferior a {maximum}."
                )


class IrsaClient:
    """
    Cliente síncrono para consultar curvas de luz públicas de IRSA.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        """
        Inicializa el cliente HTTP de IRSA.

        Args:
            timeout_seconds:
                Tiempo máximo de espera para cada petición HTTP.

                Si no se proporciona, se utiliza el valor definido mediante
                ``IRSA_REQUEST_TIMEOUT_SECONDS``.
        """

        resolved_timeout = (
            settings.irsa_request_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )

        if isinstance(resolved_timeout, bool) or not isinstance(
            resolved_timeout,
            (int, float),
        ):
            raise TypeError(
                "timeout_seconds debe ser un número real o None."
            )

        normalized_timeout = float(resolved_timeout)

        if not math.isfinite(normalized_timeout):
            raise ValueError(
                "timeout_seconds debe ser un número finito."
            )

        if normalized_timeout <= 0:
            raise ValueError(
                "timeout_seconds debe ser mayor que cero."
            )

        self._timeout_seconds = normalized_timeout
        self._timeout = httpx.Timeout(normalized_timeout)
    
    @property
    def timeout_seconds(self) -> float:
        """
        Devuelve el timeout configurado para las peticiones HTTP.
        """

        return self._timeout_seconds

    def download_light_curves(
        self,
        query: IrsaLightCurveQuery,
    ) -> bytes:
        """
        Descarga un VOTable con las curvas que cumplen la consulta.

        Args:
            query:
                Parámetros de búsqueda.

        Returns:
            Contenido XML de la respuesta en bytes.

        Raises:
            TypeError:
                Si query no es IrsaLightCurveQuery.

            IrsaConnectionError:
                Si falla la conexión.

            IrsaResponseError:
                Si IRSA devuelve una respuesta HTTP inválida o vacía.
        """

        if not isinstance(query, IrsaLightCurveQuery):
            raise TypeError(
                "query debe ser una instancia de IrsaLightCurveQuery."
            )

        parameters = query.to_query_parameters()

        logger.info(
            "Consultando curvas de luz en IRSA. "
            "ra=%.8f dec=%.8f radius_degrees=%.8f "
            "radius_arcseconds=%.4f band=%s "
            "minimum_observations=%d "
            "bad_catalog_flags_mask=%s "
            "timeout_seconds=%.2f",
            query.right_ascension,
            query.declination,
            query.radius_degrees,
            query.radius_degrees * 3600.0,
            query.band.value,
            query.minimum_observations,
            query.bad_catalog_flags_mask,
            self._timeout_seconds,
        )

        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Kilo-Hoku-ETL/0.1",
                    "Accept": (
                        "application/x-votable+xml, "
                        "application/xml, text/xml"
                    ),
                },
            ) as client:
                response = client.get(
                    IRSA_ZTF_LIGHT_CURVE_URL,
                    params=parameters,
                )

                response.raise_for_status()

        except httpx.TimeoutException as error:
            raise IrsaConnectionError(
                "La consulta a IRSA ha superado el tiempo máximo."
            ) from error

        except httpx.RequestError as error:
            raise IrsaConnectionError(
                "No se pudo conectar con la API de IRSA."
            ) from error

        except httpx.HTTPStatusError as error:
            response_preview = error.response.text.strip()[:500]

            logger.error(
                "IRSA devolvió una respuesta HTTP inválida. "
                "status_code=%d response=%r",
                error.response.status_code,
                response_preview,
            )

            raise IrsaResponseError(
                "IRSA devolvió un estado HTTP no satisfactorio: "
                f"{error.response.status_code}. "
                f"Respuesta: {response_preview!r}"
            ) from error

        content = response.content

        if not content.strip():
            raise IrsaResponseError(
                "IRSA devolvió una respuesta vacía."
            )

        content_preview = content.lstrip()[:200].lower()

        if b"<votable" not in content_preview:
            content_type = response.headers.get(
                "content-type",
                "desconocido",
            )

            raise IrsaResponseError(
                "La respuesta de IRSA no parece ser un VOTable. "
                f"Content-Type recibido: {content_type!r}."
            )

        logger.info(
            "Respuesta de IRSA recibida correctamente. "
            "band=%s bytes=%d",
            query.band.value,
            len(content),
        )

        return content