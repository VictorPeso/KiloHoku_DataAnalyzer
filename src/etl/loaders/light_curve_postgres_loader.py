"""
Loader de curvas de luz para PostgreSQL.

Este módulo implementa la etapa de carga de curvas de luz:

    alert_id + list[LightCurve]
        ↓
    LightCurvePostgresLoader
        ↓
    StarCandidateRepository
        ↓
    LightCurveRepository
        ↓
    PostgreSQL

El loader resuelve el candidato mediante su identificador ZTF externo,
por ejemplo:

    ZTF17aaaacsm

Después utiliza la clave primaria interna del candidato para relacionar las
curvas de luz y sus observaciones.

Toda la operación se ejecuta dentro de una única transacción.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.exc import SQLAlchemyError

from etl.database.repositories import (
    LightCurveRepository,
    SaveLightCurvesResult,
    StarCandidateRepository,
)
from etl.database.session import session_scope
from etl.domain.entities import LightCurve
from etl.logger import get_logger


logger = get_logger(__name__)


class LightCurveLoadingError(RuntimeError):
    """
    Error producido durante la carga de curvas de luz.
    """


class LightCurveCandidateNotFoundError(LightCurveLoadingError):
    """
    Error producido cuando no existe el candidato indicado.
    """


@dataclass(frozen=True, slots=True)
class LightCurvePostgresLoadResult:
    """
    Resultado de cargar curvas de luz en PostgreSQL.

    Attributes:
        alert_id:
            Identificador externo del candidato ZTF.

        star_candidate_id:
            Identificador interno del candidato en PostgreSQL.

        processed_curves:
            Número total de curvas procesadas.

        inserted_curves:
            Número de curvas nuevas insertadas.

        updated_curves:
            Número de curvas existentes actualizadas.

        stored_observations:
            Número total de observaciones recibidas y almacenadas.

        elapsed_seconds:
            Tiempo total empleado en la carga.
    """

    alert_id: str
    star_candidate_id: int

    processed_curves: int
    inserted_curves: int
    updated_curves: int
    stored_observations: int

    elapsed_seconds: float

    @property
    def changed_curves(self) -> int:
        """
        Devuelve el número total de curvas insertadas o actualizadas.
        """

        return self.inserted_curves + self.updated_curves

    @property
    def insert_rate(self) -> float:
        """
        Devuelve el porcentaje de curvas insertadas.
        """

        if self.processed_curves == 0:
            return 0.0

        return (
            self.inserted_curves
            / self.processed_curves
        ) * 100.0

    @property
    def update_rate(self) -> float:
        """
        Devuelve el porcentaje de curvas actualizadas.
        """

        if self.processed_curves == 0:
            return 0.0

        return (
            self.updated_curves
            / self.processed_curves
        ) * 100.0


class LightCurvePostgresLoader:
    """
    Carga curvas de luz y observaciones en PostgreSQL.

    El candidato se identifica mediante su ``alert_id``:

        ZTF17aaaacsm

    La relación persistente se realiza mediante:

        light_curves.star_candidate_id
            → star_candidates.id

    El loader utiliza una única transacción. Si cualquiera de las curvas
    falla, se ejecutará rollback y no quedará una carga parcial.
    """

    def load(
        self,
        *,
        alert_id: str,
        light_curves: Iterable[LightCurve],
    ) -> LightCurvePostgresLoadResult:
        """
        Inserta o actualiza las curvas de un candidato.

        Args:
            alert_id:
                Identificador externo único del candidato.

            light_curves:
                Curvas de luz que deben almacenarse.

        Returns:
            Resumen de la operación de carga.

        Raises:
            TypeError:
                Si los argumentos no tienen los tipos esperados.

            ValueError:
                Si ``alert_id`` está vacío.

            LightCurveCandidateNotFoundError:
                Si no existe el candidato en PostgreSQL.

            LightCurveLoadingError:
                Si se produce un error durante la persistencia.
        """

        start_time = perf_counter()

        normalized_alert_id = self._normalize_alert_id(alert_id)
        curve_list = self._materialize_light_curves(light_curves)

        logger.info(
            "Iniciando carga de curvas de luz. "
            "alert_id=%s curves=%d observations=%d",
            normalized_alert_id,
            len(curve_list),
            sum(
                curve.observation_count
                for curve in curve_list
            ),
        )

        if not curve_list:
            logger.warning(
                "No se han recibido curvas para cargar. alert_id=%s",
                normalized_alert_id,
            )

        try:
            (
                star_candidate_id,
                save_result,
            ) = self._save_light_curves(
                alert_id=normalized_alert_id,
                light_curves=curve_list,
            )

        except LightCurveCandidateNotFoundError:
            raise

        except SQLAlchemyError as error:
            logger.exception(
                "La carga de curvas ha fallado debido a un error "
                "de SQLAlchemy. alert_id=%s curves=%d",
                normalized_alert_id,
                len(curve_list),
            )

            raise LightCurveLoadingError(
                "No se pudieron guardar las curvas de luz en PostgreSQL."
            ) from error

        except Exception as error:
            logger.exception(
                "La carga de curvas de luz ha fallado. "
                "alert_id=%s curves=%d",
                normalized_alert_id,
                len(curve_list),
            )

            raise LightCurveLoadingError(
                "Se produjo un error inesperado durante la carga "
                "de curvas de luz."
            ) from error

        elapsed_seconds = perf_counter() - start_time

        result = LightCurvePostgresLoadResult(
            alert_id=normalized_alert_id,
            star_candidate_id=star_candidate_id,
            processed_curves=save_result.processed,
            inserted_curves=save_result.inserted,
            updated_curves=save_result.updated,
            stored_observations=save_result.observations,
            elapsed_seconds=elapsed_seconds,
        )

        logger.info(
            "Carga de curvas completada. "
            "alert_id=%s star_candidate_id=%d "
            "processed=%d inserted=%d updated=%d observations=%d "
            "elapsed_seconds=%.4f",
            result.alert_id,
            result.star_candidate_id,
            result.processed_curves,
            result.inserted_curves,
            result.updated_curves,
            result.stored_observations,
            result.elapsed_seconds,
        )

        return result

    @staticmethod
    def _save_light_curves(
        *,
        alert_id: str,
        light_curves: list[LightCurve],
    ) -> tuple[int, SaveLightCurvesResult]:
        """
        Ejecuta la persistencia dentro de una única transacción.

        Args:
            alert_id:
                Identificador externo del candidato.

            light_curves:
                Curvas validadas que deben almacenarse.

        Returns:
            Tupla con:

            - Identificador interno del candidato.
            - Resultado generado por LightCurveRepository.

        Raises:
            LightCurveCandidateNotFoundError:
                Si el candidato no está almacenado.
        """

        with session_scope() as session:
            candidate_repository = StarCandidateRepository(session)
            light_curve_repository = LightCurveRepository(session)

            candidate = candidate_repository.get_by_alert_id(
                alert_id
            )

            if candidate is None:
                logger.error(
                    "No existe el candidato solicitado para la carga "
                    "de curvas. alert_id=%s",
                    alert_id,
                )

                raise LightCurveCandidateNotFoundError(
                    "No existe ningún candidato almacenado con "
                    f"alert_id={alert_id!r}."
                )

            save_result = light_curve_repository.save_many(
                star_candidate_id=candidate.id,
                light_curves=light_curves,
            )

            return candidate.id, save_result

    @staticmethod
    def _materialize_light_curves(
        light_curves: Iterable[LightCurve],
    ) -> list[LightCurve]:
        """
        Materializa y valida la colección de curvas.

        Materializar el iterable permite:

        - Conocer el número total de curvas.
        - Evitar consumir generadores varias veces.
        - Validar todas las curvas antes de abrir la transacción.
        - Calcular el número total de observaciones.

        Args:
            light_curves:
                Iterable que debe convertirse en lista.

        Returns:
            Lista validada de curvas.

        Raises:
            TypeError:
                Si el argumento no es iterable o contiene elementos que no
                sean LightCurve.
        """

        if isinstance(light_curves, (str, bytes)):
            raise TypeError(
                "light_curves debe ser una colección de LightCurve."
            )

        try:
            curve_list = list(light_curves)
        except TypeError as error:
            raise TypeError(
                "light_curves debe ser una colección iterable."
            ) from error

        for index, light_curve in enumerate(curve_list):
            if not isinstance(light_curve, LightCurve):
                raise TypeError(
                    "Todos los elementos deben ser LightCurve. "
                    f"Elemento inválido en la posición {index}: "
                    f"{type(light_curve).__name__}."
                )

        return curve_list

    @staticmethod
    def _normalize_alert_id(
        alert_id: str,
    ) -> str:
        """
        Valida y normaliza el identificador externo del candidato.

        Args:
            alert_id:
                Identificador como ``ZTF17aaaacsm``.

        Returns:
            Identificador sin espacios exteriores.

        Raises:
            TypeError:
                Si el identificador no es un string.

            ValueError:
                Si está vacío.
        """

        if not isinstance(alert_id, str):
            raise TypeError(
                "alert_id debe ser de tipo str."
            )

        normalized_alert_id = alert_id.strip()

        if not normalized_alert_id:
            raise ValueError(
                "alert_id no puede estar vacío."
            )

        return normalized_alert_id