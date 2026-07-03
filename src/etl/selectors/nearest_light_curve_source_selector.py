"""
Selector de fuentes ZTF por proximidad angular.

Una consulta posicional a IRSA puede encontrar varias fuentes dentro del
radio de búsqueda. Este selector aplica el criterio acordado para asociar
una fuente al punto astronómico estudiado:

    seleccionar la fuente con menor separación angular

La selección se realiza independientemente para cada banda fotométrica.

El número de observaciones no constituye el criterio principal. Solamente
se utiliza como mecanismo de desempate cuando dos fuentes tienen una
distancia angular equivalente dentro de la tolerancia configurada.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math

from etl.domain.entities import IrsaLightCurveSource
from etl.domain.value_objects import PhotometricBand
from etl.logger import get_logger

from etl.selectors.exceptions import (
    LightCurveSourceSelectionError,
)


logger = get_logger(__name__)



@dataclass(frozen=True, slots=True)
class NearestSourceSelection:
    """
    Resultado detallado de seleccionar una fuente para una banda.

    Attributes:
        band:
            Banda fotométrica procesada.

        selected_source:
            Fuente seleccionada por proximidad.

        candidate_count:
            Número de fuentes consideradas para la banda.

        discarded_sources:
            Fuentes no seleccionadas, ordenadas por el mismo criterio
            utilizado durante la selección.
    """

    band: PhotometricBand
    selected_source: IrsaLightCurveSource
    candidate_count: int
    discarded_sources: tuple[IrsaLightCurveSource, ...]

    def __post_init__(self) -> None:
        """
        Valida la coherencia del resultado.
        """

        normalized_band = PhotometricBand.from_value(self.band)

        object.__setattr__(
            self,
            "band",
            normalized_band,
        )

        if not isinstance(
            self.selected_source,
            IrsaLightCurveSource,
        ):
            raise TypeError(
                "selected_source debe ser una instancia de "
                "IrsaLightCurveSource."
            )

        if self.selected_source.band is not normalized_band:
            raise ValueError(
                "La banda de selected_source no coincide con la banda "
                "del resultado."
            )

        if (
            isinstance(self.candidate_count, bool)
            or not isinstance(self.candidate_count, int)
        ):
            raise TypeError(
                "candidate_count debe ser un número entero."
            )

        if self.candidate_count < 1:
            raise ValueError(
                "candidate_count debe ser mayor que cero."
            )

        if self.candidate_count != (
            1 + len(self.discarded_sources)
        ):
            raise ValueError(
                "candidate_count no coincide con el número de fuentes "
                "incluidas en el resultado."
            )

        for source in self.discarded_sources:
            if not isinstance(source, IrsaLightCurveSource):
                raise TypeError(
                    "Todos los elementos de discarded_sources deben ser "
                    "IrsaLightCurveSource."
                )

            if source.band is not normalized_band:
                raise ValueError(
                    "Todas las fuentes descartadas deben pertenecer a la "
                    "misma banda que la fuente seleccionada."
                )


class NearestLightCurveSourceSelector:
    """
    Selecciona las fuentes ZTF más próximas al punto estudiado.

    El selector no calcula distancias. Espera recibir entidades
    ``IrsaLightCurveSource`` cuyo campo ``angular_distance_arcsec`` ya haya
    sido calculado por el transformer.

    Criterios de ordenación:

    1. Menor distancia angular.
    2. Mayor número de observaciones limpias, solo como desempate.
    3. Mayor número total de observaciones, solo como desempate.
    4. Menor identificador ZTF, para obtener resultados deterministas.
    """

    def __init__(
        self,
        *,
        distance_tolerance_arcsec: float = 1e-9,
    ) -> None:
        """
        Inicializa el selector.

        Args:
            distance_tolerance_arcsec:
                Tolerancia utilizada para considerar equivalentes dos
                distancias angulares.

                El valor no limita la distancia máxima permitida. El radio
                máximo ya viene determinado por la consulta posicional a
                IRSA.

        Raises:
            TypeError:
                Si la tolerancia no es un número real.

            ValueError:
                Si la tolerancia no es finita o es negativa.
        """

        if (
            isinstance(distance_tolerance_arcsec, bool)
            or not isinstance(
                distance_tolerance_arcsec,
                (int, float),
            )
        ):
            raise TypeError(
                "distance_tolerance_arcsec debe ser un número real."
            )

        normalized_tolerance = float(
            distance_tolerance_arcsec
        )

        if not math.isfinite(normalized_tolerance):
            raise ValueError(
                "distance_tolerance_arcsec debe ser un número finito."
            )

        if normalized_tolerance < 0:
            raise ValueError(
                "distance_tolerance_arcsec no puede ser negativo."
            )

        self._distance_tolerance_arcsec = (
            normalized_tolerance
        )

    @property
    def distance_tolerance_arcsec(self) -> float:
        """
        Devuelve la tolerancia angular utilizada en los desempates.
        """

        return self._distance_tolerance_arcsec

    def select(
        self,
        sources: Iterable[IrsaLightCurveSource],
        *,
        band: PhotometricBand | str | None = None,
    ) -> IrsaLightCurveSource | None:
        """
        Selecciona la fuente más próxima.

        Args:
            sources:
                Fuentes candidatas que deben evaluarse.

            band:
                Banda opcional por la que filtrar las fuentes.

                Si no se proporciona, todas las fuentes recibidas compiten
                entre sí. Para el flujo normal se recomienda indicar la
                banda o utilizar ``select_per_band()``.

        Returns:
            Fuente más próxima o None si no existen candidatas para la
            selección solicitada.

        Raises:
            TypeError:
                Si ``sources`` no es iterable o contiene elementos de otro
                tipo.
        """

        source_list = self._materialize_sources(sources)

        if band is not None:
            normalized_band = PhotometricBand.from_value(band)

            source_list = [
                source
                for source in source_list
                if source.band is normalized_band
            ]

        if not source_list:
            return None

        ordered_sources = self._sort_sources(source_list)

        return ordered_sources[0]

    def select_detailed(
        self,
        sources: Iterable[IrsaLightCurveSource],
        *,
        band: PhotometricBand | str,
    ) -> NearestSourceSelection | None:
        """
        Selecciona una fuente y devuelve información detallada.

        Args:
            sources:
                Fuentes candidatas.

            band:
                Banda cuya fuente debe seleccionarse.

        Returns:
            Resultado detallado o None si no hay fuentes de la banda.
        """

        normalized_band = PhotometricBand.from_value(band)
        source_list = self._materialize_sources(sources)

        matching_sources = [
            source
            for source in source_list
            if source.band is normalized_band
        ]

        if not matching_sources:
            logger.info(
                "No se han encontrado fuentes candidatas para la banda. "
                "band=%s",
                normalized_band.value,
            )
            return None

        ordered_sources = self._sort_sources(
            matching_sources
        )

        selected_source = ordered_sources[0]
        discarded_sources = tuple(ordered_sources[1:])

        result = NearestSourceSelection(
            band=normalized_band,
            selected_source=selected_source,
            candidate_count=len(ordered_sources),
            discarded_sources=discarded_sources,
        )

        logger.info(
            "Fuente ZTF seleccionada por proximidad. "
            "band=%s selected_oid=%d distance_arcsec=%.9f "
            "clean_observations=%d total_observations=%d "
            "candidate_count=%d",
            result.band.value,
            result.selected_source.ztf_object_id,
            result.selected_source.angular_distance_arcsec,
            result.selected_source.clean_observation_count,
            result.selected_source.observation_count,
            result.candidate_count,
        )

        for discarded_source in result.discarded_sources:
            logger.debug(
                "Fuente ZTF descartada. "
                "band=%s discarded_oid=%d distance_arcsec=%.9f "
                "selected_oid=%d reason=farther_than_selected_source",
                result.band.value,
                discarded_source.ztf_object_id,
                discarded_source.angular_distance_arcsec,
                result.selected_source.ztf_object_id,
            )

        return result

    def select_per_band(
        self,
        sources: Iterable[IrsaLightCurveSource],
        *,
        bands: Iterable[PhotometricBand | str] | None = None,
    ) -> dict[PhotometricBand, IrsaLightCurveSource]:
        """
        Selecciona la fuente más próxima para cada banda.

        Args:
            sources:
                Fuentes candidatas encontradas por IRSA.

            bands:
                Bandas que deben procesarse.

                Si no se proporciona, se procesan todas las bandas presentes
                en las fuentes recibidas.

        Returns:
            Diccionario cuya clave es la banda y cuyo valor es la fuente
            seleccionada.

            Las bandas sin fuentes no aparecen en el resultado.
        """

        source_list = self._materialize_sources(sources)

        if not source_list:
            logger.info(
                "No se han recibido fuentes candidatas para seleccionar."
            )
            return {}

        selected_bands = self._resolve_bands(
            source_list,
            bands=bands,
        )

        selections: dict[
            PhotometricBand,
            IrsaLightCurveSource,
        ] = {}

        for band in selected_bands:
            selection = self.select_detailed(
                source_list,
                band=band,
            )

            if selection is not None:
                selections[band] = (
                    selection.selected_source
                )

        logger.info(
            "Selección de fuentes IRSA completada. "
            "input_sources=%d requested_bands=%d selected_sources=%d",
            len(source_list),
            len(selected_bands),
            len(selections),
        )

        return selections

    def select_per_band_detailed(
        self,
        sources: Iterable[IrsaLightCurveSource],
        *,
        bands: Iterable[PhotometricBand | str] | None = None,
    ) -> dict[PhotometricBand, NearestSourceSelection]:
        """
        Selecciona una fuente por banda y devuelve resultados detallados.

        Returns:
            Diccionario con un resultado detallado por cada banda que tenga
            fuentes candidatas.
        """

        source_list = self._materialize_sources(sources)

        if not source_list:
            return {}

        selected_bands = self._resolve_bands(
            source_list,
            bands=bands,
        )

        selections: dict[
            PhotometricBand,
            NearestSourceSelection,
        ] = {}

        for band in selected_bands:
            selection = self.select_detailed(
                source_list,
                band=band,
            )

            if selection is not None:
                selections[band] = selection

        return selections

    def _sort_sources(
        self,
        sources: list[IrsaLightCurveSource],
    ) -> list[IrsaLightCurveSource]:
        """
        Ordena las fuentes según el criterio de selección.

        Las distancias se agrupan mediante la tolerancia configurada para
        que diferencias numéricas insignificantes no alteren el desempate.
        """

        return sorted(
            sources,
            key=self._selection_key,
        )

    def _selection_key(
        self,
        source: IrsaLightCurveSource,
    ) -> tuple[float, int, int, int]:
        """
        Genera la clave de ordenación de una fuente.
        """

        if self._distance_tolerance_arcsec == 0:
            normalized_distance = (
                source.angular_distance_arcsec
            )
        else:
            normalized_distance = (
                round(
                    source.angular_distance_arcsec
                    / self._distance_tolerance_arcsec
                )
                * self._distance_tolerance_arcsec
            )

        return (
            normalized_distance,
            -source.clean_observation_count,
            -source.observation_count,
            source.ztf_object_id,
        )

    @staticmethod
    def _materialize_sources(
        sources: Iterable[IrsaLightCurveSource],
    ) -> list[IrsaLightCurveSource]:
        """
        Materializa y valida una colección de fuentes.
        """

        if isinstance(sources, (str, bytes)):
            raise TypeError(
                "sources debe ser una colección de "
                "IrsaLightCurveSource."
            )

        try:
            source_list = list(sources)
        except TypeError as error:
            raise TypeError(
                "sources debe ser una colección iterable."
            ) from error

        for index, source in enumerate(source_list):
            if not isinstance(source, IrsaLightCurveSource):
                raise TypeError(
                    "Todos los elementos de sources deben ser "
                    "IrsaLightCurveSource. "
                    f"Elemento inválido en la posición {index}: "
                    f"{type(source).__name__}."
                )

        return source_list

    @staticmethod
    def _resolve_bands(
        sources: list[IrsaLightCurveSource],
        *,
        bands: Iterable[PhotometricBand | str] | None,
    ) -> tuple[PhotometricBand, ...]:
        """
        Determina las bandas que deben procesarse.
        """

        if bands is None:
            return tuple(
                sorted(
                    {
                        source.band
                        for source in sources
                    },
                    key=lambda band: band.value,
                )
            )

        if isinstance(bands, (str, bytes)):
            raise TypeError(
                "bands debe ser una colección de bandas, no una cadena."
            )

        try:
            normalized_bands = [
                PhotometricBand.from_value(band)
                for band in bands
            ]
        except TypeError as error:
            raise TypeError(
                "bands debe ser una colección iterable."
            ) from error

        # Elimina duplicados conservando el orden proporcionado.
        return tuple(dict.fromkeys(normalized_bands))