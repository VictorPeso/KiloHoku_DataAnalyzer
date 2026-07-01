"""
Repositorio de candidatos estelares.

Este módulo encapsula las operaciones de lectura y escritura relacionadas
con StarCandidateModel.

El repositorio:

- Recibe una sesión SQLAlchemy ya creada.
- No crea conexiones por su cuenta.
- No ejecuta commit ni rollback.
- Convierte entidades de dominio en modelos ORM.
- Permite insertar, consultar, actualizar y eliminar candidatos.
- Evita que la pipeline tenga que conocer detalles de SQLAlchemy.

La transacción debe gestionarse desde fuera mediante session_scope().
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from etl.database.models import StarCandidateModel
from etl.domain.entities import StarCandidate
from etl.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SaveManyResult:
    """
    Resultado de guardar una colección de candidatos.

    Attributes:
        inserted:
            Número de candidatos nuevos insertados.

        updated:
            Número de candidatos existentes actualizados.

        processed:
            Número total de candidatos procesados.
    """

    inserted: int
    updated: int
    processed: int


class StarCandidateRepository:
    """
    Repositorio de acceso a candidatos estelares.

    La sesión se proporciona mediante inyección de dependencias:

        with session_scope() as session:
            repository = StarCandidateRepository(session)
            repository.save(candidate)

    El commit se realizará automáticamente al finalizar correctamente el
    bloque session_scope().
    """

    def __init__(self, session: Session) -> None:
        """
        Inicializa el repositorio.

        Args:
            session:
                Sesión SQLAlchemy activa.

        Raises:
            TypeError:
                Si el objeto recibido no es una Session.
        """

        if not isinstance(session, Session):
            raise TypeError(
                "session debe ser una instancia de sqlalchemy.orm.Session."
            )

        self._session = session

    @property
    def session(self) -> Session:
        """
        Devuelve la sesión utilizada por el repositorio.
        """

        return self._session

    def get_by_id(
        self,
        candidate_id: int,
    ) -> StarCandidateModel | None:
        """
        Busca un candidato mediante su clave primaria interna.

        Args:
            candidate_id:
                Identificador interno del registro.

        Returns:
            Modelo encontrado o None.
        """

        if candidate_id <= 0:
            raise ValueError(
                "candidate_id debe ser un número entero positivo."
            )

        return self._session.get(
            StarCandidateModel,
            candidate_id,
        )

    def get_by_alert_url(
        self,
        alert_url: str,
    ) -> StarCandidateModel | None:
        """
        Busca un candidato mediante la URL de la alerta.

        Args:
            alert_url:
                URL única de la alerta astronómica.

        Returns:
            Modelo encontrado o None.
        """

        normalized_alert_url = self._normalize_required_string(
            alert_url,
            field_name="alert_url",
        )

        statement = select(StarCandidateModel).where(
            StarCandidateModel.alert_url == normalized_alert_url
        )

        return self._session.scalar(statement)

    def get_by_alert_id(
        self,
        alert_id: str,
    ) -> StarCandidateModel | None:
        """
        Busca un candidato mediante su identificador ZTF.

        Ejemplo:

            ZTF17aaaacsm

        Args:
            alert_id:
                Identificador externo único del candidato.

        Returns:
            Modelo encontrado o None.
        """

        normalized_alert_id = self._normalize_required_string(
            alert_id,
            field_name="alert_id",
        )

        statement = select(StarCandidateModel).where(
            StarCandidateModel.alert_id == normalized_alert_id
        )

        return self._session.scalar(statement)

    def get_by_gaia_dr3_name(
        self,
        gaia_dr3_name: str,
    ) -> list[StarCandidateModel]:
        """
        Obtiene todas las alertas relacionadas con una fuente de Gaia DR3.

        Una misma fuente de Gaia puede estar asociada a varias alertas.

        Args:
            gaia_dr3_name:
                Identificador de Gaia DR3.

        Returns:
            Lista de modelos encontrados.
        """

        normalized_name = self._normalize_required_string(
            gaia_dr3_name,
            field_name="gaia_dr3_name",
        )

        statement = (
            select(StarCandidateModel)
            .where(
                StarCandidateModel.gaia_dr3_name == normalized_name
            )
            .order_by(
                StarCandidateModel.observation_date.asc()
            )
        )

        return list(
            self._session.scalars(statement).all()
        )

    def exists_by_alert_url(
        self,
        alert_url: str,
    ) -> bool:
        """
        Comprueba si ya existe una alerta.

        Args:
            alert_url:
                URL de la alerta.

        Returns:
            True cuando existe un registro con esa URL.
        """

        normalized_alert_url = self._normalize_required_string(
            alert_url,
            field_name="alert_url",
        )

        statement = select(
            select(StarCandidateModel.id)
            .where(
                StarCandidateModel.alert_url
                == normalized_alert_url
            )
            .exists()
        )

        return bool(self._session.scalar(statement))
    
    def exists_by_alert_id(
        self,
        alert_id: str,
    ) -> bool:
        """
        Comprueba si existe un candidato con el alert_id indicado.

        Args:
            alert_id:
                Identificador externo del candidato.

        Returns:
            True si el candidato existe.
        """

        normalized_alert_id = self._normalize_required_string(
            alert_id,
            field_name="alert_id",
        )

        statement = select(
            select(StarCandidateModel.id)
            .where(
                StarCandidateModel.alert_id
                == normalized_alert_id
            )
            .exists()
        )

        return bool(self._session.scalar(statement))

    def count(self) -> int:
        """
        Devuelve el número total de candidatos almacenados.
        """

        statement = select(
            func.count(StarCandidateModel.id)
        )

        return int(
            self._session.scalar(statement) or 0
        )

    def list_all(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StarCandidateModel]:
        """
        Obtiene candidatos ordenados por fecha de observación.

        Args:
            limit:
                Número máximo de registros. Si es None, no se aplica límite.

            offset:
                Número de registros que deben omitirse desde el principio.

        Returns:
            Lista de modelos ORM.

        Raises:
            ValueError:
                Si limit u offset contienen valores inválidos.
        """

        if limit is not None and limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero o None."
            )

        if offset < 0:
            raise ValueError(
                "offset no puede ser negativo."
            )

        statement = (
            select(StarCandidateModel)
            .order_by(
                StarCandidateModel.observation_date.asc(),
                StarCandidateModel.id.asc(),
            )
            .offset(offset)
        )

        if limit is not None:
            statement = statement.limit(limit)

        return list(
            self._session.scalars(statement).all()
        )

    def save(
        self,
        candidate: StarCandidate,
    ) -> StarCandidateModel:
        """
        Inserta un nuevo candidato.

        Este método no comprueba previamente si la alerta ya existe. Si se
        intenta insertar una URL duplicada, PostgreSQL generará un error por
        la restricción UNIQUE.

        Args:
            candidate:
                Entidad de dominio que debe almacenarse.

        Returns:
            Modelo ORM añadido a la sesión.

        Notes:
            Se ejecuta flush para enviar el INSERT a PostgreSQL y obtener la
            clave primaria, pero no se ejecuta commit.
        """

        self._validate_candidate(candidate)

        model = StarCandidateModel.from_domain(candidate)

        self._session.add(model)
        self._session.flush()

        logger.debug(
            "Candidato añadido a la sesión. id=%s alert_id=%s",
            model.id,
            candidate.alert_id,
        )

        return model

    def save_or_update(
        self,
        candidate: StarCandidate,
    ) -> tuple[StarCandidateModel, bool]:
        """
        Inserta el candidato o actualiza el registro existente.

        La alerta se identifica mediante alert_url.

        Args:
            candidate:
                Entidad que debe persistirse.

        Returns:
            Tupla formada por:

            - El modelo insertado o actualizado.
            - True si se insertó un registro nuevo.
            - False si se actualizó un registro existente.
        """

        self._validate_candidate(candidate)

        existing_model = self.get_by_alert_id(
            candidate.alert_id
        )

        if existing_model is None:
            model = self.save(candidate)

            logger.debug(
                "Nuevo candidato insertado. id=%s alert_id=%s",
                model.id,
                candidate.alert_id,
            )

            return model, True

        existing_model.update_from_domain(candidate)
        self._session.flush()

        logger.debug(
            "Candidato existente actualizado. id=%s alert_id=%s",
            existing_model.id,
            candidate.alert_id,
        )

        return existing_model, False

    def save_many(
        self,
        candidates: Iterable[StarCandidate],
    ) -> SaveManyResult:
        """
        Inserta o actualiza una colección de candidatos.

        Args:
            candidates:
                Entidades que deben persistirse.

        Returns:
            Resumen de registros insertados y actualizados.

        Notes:
            Esta implementación prioriza claridad y validación individual.
            Para conjuntos de datos mucho mayores se podrá sustituir por una
            operación bulk o un upsert específico de PostgreSQL.
        """

        inserted = 0
        updated = 0
        processed = 0

        for candidate in candidates:
            _, was_inserted = self.save_or_update(candidate)

            processed += 1

            if was_inserted:
                inserted += 1
            else:
                updated += 1

        logger.info(
            "Colección de candidatos preparada para persistencia. "
            "processed=%d inserted=%d updated=%d",
            processed,
            inserted,
            updated,
        )

        return SaveManyResult(
            inserted=inserted,
            updated=updated,
            processed=processed,
        )

    def delete(
        self,
        model: StarCandidateModel,
    ) -> None:
        """
        Elimina un modelo ORM.

        Args:
            model:
                Registro que debe eliminarse.

        Raises:
            TypeError:
                Si el objeto no es StarCandidateModel.
        """

        if not isinstance(model, StarCandidateModel):
            raise TypeError(
                "model debe ser una instancia de StarCandidateModel."
            )

        candidate_id = model.id
        alert_id = model.alert_id

        self._session.delete(model)
        self._session.flush()

        logger.debug(
            "Candidato eliminado. id=%s alert_id=%s",
            candidate_id,
            alert_id,
        )

    def delete_by_alert_url(
        self,
        alert_url: str,
    ) -> bool:
        """
        Elimina un candidato mediante su URL de alerta.

        Args:
            alert_url:
                URL de la alerta que debe eliminarse.

        Returns:
            True si se encontró y eliminó el registro.
            False si no existía.
        """

        model = self.get_by_alert_url(alert_url)

        if model is None:
            return False

        self.delete(model)
        return True

    def find_by_object_class(
        self,
        object_class: str,
        *,
        limit: int | None = None,
    ) -> list[StarCandidateModel]:
        """
        Busca candidatos por su clasificación externa.

        Args:
            object_class:
                Clase astronómica que debe buscarse.

            limit:
                Número máximo de resultados.

        Returns:
            Lista de modelos coincidentes.
        """

        normalized_class = self._normalize_required_string(
            object_class,
            field_name="object_class",
        )

        if limit is not None and limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero o None."
            )

        statement = (
            select(StarCandidateModel)
            .where(
                StarCandidateModel.object_class
                == normalized_class
            )
            .order_by(
                StarCandidateModel.observation_date.asc()
            )
        )

        if limit is not None:
            statement = statement.limit(limit)

        return list(
            self._session.scalars(statement).all()
        )

    def find_with_resources(
        self,
    ) -> list[StarCandidateModel]:
        """
        Obtiene candidatos que tienen archivo de datos y gráfica.
        """

        statement = (
            select(StarCandidateModel)
            .where(
                StarCandidateModel.data_file_url.is_not(None),
                StarCandidateModel.plot_url.is_not(None),
            )
            .order_by(
                StarCandidateModel.observation_date.asc()
            )
        )

        return list(
            self._session.scalars(statement).all()
        )

    def find_without_resources(
        self,
    ) -> list[StarCandidateModel]:
        """
        Obtiene candidatos sin archivo de datos o sin gráfica.
        """

        statement = (
            select(StarCandidateModel)
            .where(
                (
                    StarCandidateModel.data_file_url.is_(None)
                )
                | (
                    StarCandidateModel.plot_url.is_(None)
                )
            )
            .order_by(
                StarCandidateModel.observation_date.asc()
            )
        )

        return list(
            self._session.scalars(statement).all()
        )

    def find_with_spectrum(
        self,
    ) -> list[StarCandidateModel]:
        """
        Obtiene candidatos que disponen de espectro.
        """

        statement = (
            select(StarCandidateModel)
            .where(
                StarCandidateModel.has_spectrum.is_(True)
            )
            .order_by(
                StarCandidateModel.observation_date.asc()
            )
        )

        return list(
            self._session.scalars(statement).all()
        )

    @staticmethod
    def to_domain_list(
        models: Sequence[StarCandidateModel],
    ) -> list[StarCandidate]:
        """
        Convierte una colección de modelos ORM a entidades de dominio.

        Args:
            models:
                Modelos que deben convertirse.

        Returns:
            Lista de entidades StarCandidate.
        """

        return [
            model.to_domain()
            for model in models
        ]

    @staticmethod
    def _validate_candidate(
        candidate: StarCandidate,
    ) -> None:
        """
        Comprueba que el objeto sea una entidad StarCandidate.
        """

        if not isinstance(candidate, StarCandidate):
            raise TypeError(
                "candidate debe ser una instancia de StarCandidate."
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