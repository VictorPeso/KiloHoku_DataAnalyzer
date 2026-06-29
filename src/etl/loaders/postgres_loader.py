"""
Loader de candidatos estelares para PostgreSQL.

Este módulo implementa la etapa Load del proceso ETL:

    list[StarCandidate]
        ↓
    PostgresLoader
        ↓
    StarCandidateRepository
        ↓
    PostgreSQL

El loader coordina la transacción y utiliza el repositorio para insertar
o actualizar los candidatos.

No contiene consultas SQL directas ni conoce los detalles internos del
modelo ORM.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.exc import SQLAlchemyError

from etl.database.repositories import (
    SaveManyResult,
    StarCandidateRepository,
)
from etl.database.session import session_scope
from etl.domain.entities import StarCandidate
from etl.logger import get_logger


logger = get_logger(__name__)


class LoadingError(RuntimeError):
    """
    Error producido durante la carga de datos en PostgreSQL.
    """


@dataclass(frozen=True, slots=True)
class PostgresLoadResult:
    """
    Resultado de una operación de carga en PostgreSQL.

    Attributes:
        processed:
            Número total de candidatos procesados.

        inserted:
            Número de candidatos nuevos insertados.

        updated:
            Número de candidatos existentes actualizados.

        elapsed_seconds:
            Tiempo empleado durante la operación.
    """

    processed: int
    inserted: int
    updated: int
    elapsed_seconds: float

    @property
    def changed_records(self) -> int:
        """
        Número total de registros insertados o actualizados.
        """

        return self.inserted + self.updated

    @property
    def insert_rate(self) -> float:
        """
        Porcentaje de registros que fueron insertados.

        Returns:
            Porcentaje comprendido entre 0 y 100.
        """

        if self.processed == 0:
            return 0.0

        return (self.inserted / self.processed) * 100.0

    @property
    def update_rate(self) -> float:
        """
        Porcentaje de registros que fueron actualizados.

        Returns:
            Porcentaje comprendido entre 0 y 100.
        """

        if self.processed == 0:
            return 0.0

        return (self.updated / self.processed) * 100.0


class PostgresLoader:
    """
    Carga candidatos estelares válidos en PostgreSQL.

    El loader utiliza una única transacción para toda la colección.

    Si la carga termina correctamente:

        commit

    Si se produce cualquier excepción:

        rollback

    Esto evita que una importación quede parcialmente almacenada.
    """

    def load(
        self,
        candidates: Iterable[StarCandidate],
    ) -> PostgresLoadResult:
        """
        Inserta o actualiza una colección de candidatos.

        Cada candidato se identifica mediante ``alert_url``:

        - Si no existe, se inserta.
        - Si ya existe, se actualiza.

        Args:
            candidates:
                Colección de entidades StarCandidate que deben persistirse.

        Returns:
            Resumen de la operación de carga.

        Raises:
            TypeError:
                Si alguno de los elementos no es StarCandidate.

            LoadingError:
                Si se produce un error durante la persistencia.
        """

        start_time = perf_counter()

        candidate_list = self._materialize_candidates(candidates)

        logger.info(
            "Iniciando carga de candidatos en PostgreSQL. candidates=%d",
            len(candidate_list),
        )

        if not candidate_list:
            logger.warning(
                "No se han recibido candidatos para cargar."
            )

            return PostgresLoadResult(
                processed=0,
                inserted=0,
                updated=0,
                elapsed_seconds=perf_counter() - start_time,
            )

        try:
            save_result = self._save_candidates(candidate_list)

        except SQLAlchemyError as error:
            logger.exception(
                "La carga en PostgreSQL ha fallado debido a un error "
                "de SQLAlchemy. candidates=%d",
                len(candidate_list),
            )

            raise LoadingError(
                "No se pudieron cargar los candidatos en PostgreSQL."
            ) from error

        except Exception as error:
            logger.exception(
                "La carga en PostgreSQL ha fallado. candidates=%d",
                len(candidate_list),
            )

            raise LoadingError(
                "Se produjo un error inesperado durante la carga "
                "de candidatos."
            ) from error

        elapsed_seconds = perf_counter() - start_time

        result = PostgresLoadResult(
            processed=save_result.processed,
            inserted=save_result.inserted,
            updated=save_result.updated,
            elapsed_seconds=elapsed_seconds,
        )

        logger.info(
            "Carga en PostgreSQL completada. processed=%d inserted=%d "
            "updated=%d insert_rate=%.2f update_rate=%.2f "
            "elapsed_seconds=%.4f",
            result.processed,
            result.inserted,
            result.updated,
            result.insert_rate,
            result.update_rate,
            result.elapsed_seconds,
        )

        return result

    @staticmethod
    def _save_candidates(
        candidates: list[StarCandidate],
    ) -> SaveManyResult:
        """
        Ejecuta la persistencia dentro de una transacción.

        Args:
            candidates:
                Candidatos que deben almacenarse.

        Returns:
            Resultado generado por el repositorio.
        """

        with session_scope() as session:
            repository = StarCandidateRepository(session)

            return repository.save_many(candidates)

    @staticmethod
    def _materialize_candidates(
        candidates: Iterable[StarCandidate],
    ) -> list[StarCandidate]:
        """
        Convierte la colección recibida en una lista y valida sus elementos.

        Materializar el iterable permite:

        - Conocer el número total de candidatos.
        - Evitar consumir un generador varias veces.
        - Validar todos los elementos antes de abrir una transacción.

        Args:
            candidates:
                Iterable de entidades.

        Returns:
            Lista de candidatos validada.

        Raises:
            TypeError:
                Si el argumento no es iterable o contiene elementos de un
                tipo incorrecto.
        """

        try:
            candidate_list = list(candidates)
        except TypeError as error:
            raise TypeError(
                "candidates debe ser una colección iterable."
            ) from error

        for index, candidate in enumerate(candidate_list):
            if not isinstance(candidate, StarCandidate):
                raise TypeError(
                    "Todos los elementos deben ser StarCandidate. "
                    f"Elemento inválido en la posición {index}: "
                    f"{type(candidate).__name__}."
                )

        return candidate_list