"""
Repositorio de curvas de luz ZTF.

Este módulo encapsula las operaciones de persistencia relacionadas con:

- LightCurveModel
- LightCurveObservationModel

El repositorio recibe una sesión SQLAlchemy activa y no gestiona
directamente la transacción. El commit, rollback y cierre de la sesión
corresponden a session_scope().

La estrategia utilizada al volver a importar una curva es:

    curva existente
        ↓
    actualizar metadatos
        ↓
    eliminar observaciones anteriores
        ↓
    insertar las observaciones recién descargadas

Esta estrategia es sencilla y segura durante las primeras fases del
proyecto, porque garantiza que PostgreSQL refleje exactamente el contenido
más reciente del VOTable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from etl.database.models import (
    LightCurveModel,
    LightCurveObservationModel,
    StarCandidateModel,
)
from etl.domain.entities import LightCurve
from etl.domain.value_objects import PhotometricBand
from etl.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SaveLightCurvesResult:
    """
    Resultado de guardar una colección de curvas.

    Attributes:
        processed:
            Número total de curvas procesadas.

        inserted:
            Número de curvas nuevas insertadas.

        updated:
            Número de curvas existentes actualizadas.

        observations:
            Número total de observaciones almacenadas para las curvas
            procesadas.
    """

    processed: int
    inserted: int
    updated: int
    observations: int


class StarCandidateNotFoundError(LookupError):
    """
    Error producido cuando no existe el candidato relacionado.
    """


class LightCurveRepository:
    """
    Repositorio de acceso a curvas de luz y sus observaciones.

    Ejemplo:

        with session_scope() as session:
            repository = LightCurveRepository(session)

            repository.save_or_update(
                star_candidate_id=candidate.id,
                light_curve=curve,
            )

    El bloque session_scope() confirmará o revertirá toda la operación.
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
        light_curve_id: int,
        *,
        include_observations: bool = True,
    ) -> LightCurveModel | None:
        """
        Busca una curva mediante su clave primaria.

        Args:
            light_curve_id:
                Identificador interno de la curva.

            include_observations:
                Indica si deben cargarse también sus observaciones.

        Returns:
            Modelo encontrado o None.
        """

        self._validate_positive_integer(
            light_curve_id,
            field_name="light_curve_id",
        )

        statement = select(LightCurveModel).where(
            LightCurveModel.id == light_curve_id
        )

        if include_observations:
            statement = statement.options(
                selectinload(LightCurveModel.observations)
            )

        return self._session.scalar(statement)

    def get_by_identity(
        self,
        *,
        star_candidate_id: int,
        ztf_object_id: int,
        band: PhotometricBand | str,
        include_observations: bool = True,
    ) -> LightCurveModel | None:
        """
        Busca una curva mediante su identidad lógica.

        La identidad está formada por:

            star_candidate_id + ztf_object_id + band

        Args:
            star_candidate_id:
                Identificador interno del candidato.

            ztf_object_id:
                Identificador ``oid`` devuelto por ZTF.

            band:
                Banda fotométrica g, r o i.

            include_observations:
                Indica si deben recuperarse las observaciones.

        Returns:
            Modelo encontrado o None.
        """

        self._validate_positive_integer(
            star_candidate_id,
            field_name="star_candidate_id",
        )

        self._validate_non_negative_integer(
            ztf_object_id,
            field_name="ztf_object_id",
        )

        normalized_band = PhotometricBand.from_value(band)

        statement = select(LightCurveModel).where(
            LightCurveModel.star_candidate_id == star_candidate_id,
            LightCurveModel.ztf_object_id == ztf_object_id,
            LightCurveModel.band == normalized_band.value,
        )

        if include_observations:
            statement = statement.options(
                selectinload(LightCurveModel.observations)
            )

        return self._session.scalar(statement)

    def list_by_candidate_id(
        self,
        star_candidate_id: int,
        *,
        band: PhotometricBand | str | None = None,
        include_observations: bool = False,
    ) -> list[LightCurveModel]:
        """
        Obtiene las curvas relacionadas con un candidato.

        Args:
            star_candidate_id:
                Identificador interno del candidato.

            band:
                Filtro opcional por banda.

            include_observations:
                Indica si deben cargarse también las observaciones.

        Returns:
            Lista de curvas ordenada por banda y objeto ZTF.
        """

        self._validate_positive_integer(
            star_candidate_id,
            field_name="star_candidate_id",
        )

        statement = select(LightCurveModel).where(
            LightCurveModel.star_candidate_id == star_candidate_id
        )

        if band is not None:
            normalized_band = PhotometricBand.from_value(band)

            statement = statement.where(
                LightCurveModel.band == normalized_band.value
            )

        if include_observations:
            statement = statement.options(
                selectinload(LightCurveModel.observations)
            )

        statement = statement.order_by(
            LightCurveModel.band.asc(),
            LightCurveModel.ztf_object_id.asc(),
        )

        return list(self._session.scalars(statement).all())

    def list_by_candidate_alert_id(
        self,
        alert_id: str,
        *,
        band: PhotometricBand | str | None = None,
        include_observations: bool = False,
    ) -> list[LightCurveModel]:
        """
        Obtiene las curvas de un candidato mediante su identificador ZTF.

        Ejemplo:

            ZTF17aaaacsm

        Args:
            alert_id:
                Identificador externo del candidato.

            band:
                Banda opcional para filtrar los resultados.

            include_observations:
                Indica si deben cargarse las observaciones.

        Returns:
            Lista de curvas relacionadas.

        Raises:
            StarCandidateNotFoundError:
                Si el candidato no existe.
        """

        normalized_alert_id = self._normalize_required_string(
            alert_id,
            field_name="alert_id",
        )

        candidate_statement = select(StarCandidateModel).where(
            StarCandidateModel.alert_id == normalized_alert_id
        )

        candidate = self._session.scalar(candidate_statement)

        if candidate is None:
            raise StarCandidateNotFoundError(
                "No existe ningún candidato con "
                f"alert_id={normalized_alert_id!r}."
            )

        return self.list_by_candidate_id(
            candidate.id,
            band=band,
            include_observations=include_observations,
        )

    def count(
        self,
        *,
        star_candidate_id: int | None = None,
    ) -> int:
        """
        Cuenta las curvas almacenadas.

        Args:
            star_candidate_id:
                Si se proporciona, cuenta solamente las curvas de ese
                candidato.

        Returns:
            Número de curvas.
        """

        statement = select(func.count(LightCurveModel.id))

        if star_candidate_id is not None:
            self._validate_positive_integer(
                star_candidate_id,
                field_name="star_candidate_id",
            )

            statement = statement.where(
                LightCurveModel.star_candidate_id
                == star_candidate_id
            )

        return int(self._session.scalar(statement) or 0)

    def count_observations(
        self,
        *,
        light_curve_id: int | None = None,
    ) -> int:
        """
        Cuenta observaciones almacenadas.

        Args:
            light_curve_id:
                Si se proporciona, cuenta solo las observaciones de esa
                curva.

        Returns:
            Número de observaciones.
        """

        statement = select(
            func.count(LightCurveObservationModel.id)
        )

        if light_curve_id is not None:
            self._validate_positive_integer(
                light_curve_id,
                field_name="light_curve_id",
            )

            statement = statement.where(
                LightCurveObservationModel.light_curve_id
                == light_curve_id
            )

        return int(self._session.scalar(statement) or 0)

    def exists(
        self,
        *,
        star_candidate_id: int,
        ztf_object_id: int,
        band: PhotometricBand | str,
    ) -> bool:
        """
        Comprueba si una curva ya está almacenada.

        Args:
            star_candidate_id:
                Identificador interno del candidato.

            ztf_object_id:
                Identificador del objeto ZTF.

            band:
                Banda fotométrica.

        Returns:
            True si la curva existe.
        """

        self._validate_positive_integer(
            star_candidate_id,
            field_name="star_candidate_id",
        )

        self._validate_non_negative_integer(
            ztf_object_id,
            field_name="ztf_object_id",
        )

        normalized_band = PhotometricBand.from_value(band)

        statement = select(
            select(LightCurveModel.id)
            .where(
                LightCurveModel.star_candidate_id
                == star_candidate_id,
                LightCurveModel.ztf_object_id == ztf_object_id,
                LightCurveModel.band == normalized_band.value,
            )
            .exists()
        )

        return bool(self._session.scalar(statement))

    def save(
        self,
        *,
        star_candidate_id: int,
        light_curve: LightCurve,
    ) -> LightCurveModel:
        """
        Inserta una curva nueva con todas sus observaciones.

        Este método no comprueba si ya existe una curva con la misma
        identidad. En caso de duplicado, PostgreSQL generará un error por la
        restricción UNIQUE.

        Args:
            star_candidate_id:
                Identificador del candidato relacionado.

            light_curve:
                Curva de dominio que debe almacenarse.

        Returns:
            Modelo ORM insertado.

        Notes:
            Se ejecuta flush, pero no commit.
        """

        self._validate_light_curve(light_curve)
        self._require_candidate(star_candidate_id)

        model = LightCurveModel.from_domain(
            light_curve,
            star_candidate_id=star_candidate_id,
        )

        model.observations = self._build_observation_models(
            light_curve
        )

        model.observation_count = len(model.observations)

        self._session.add(model)
        self._session.flush()

        logger.debug(
            "Curva de luz añadida a la sesión. "
            "id=%s star_candidate_id=%s curve_key=%s observations=%d",
            model.id,
            star_candidate_id,
            model.curve_key,
            model.observation_count,
        )

        return model

    def save_or_update(
        self,
        *,
        star_candidate_id: int,
        light_curve: LightCurve,
    ) -> tuple[LightCurveModel, bool]:
        """
        Inserta una curva nueva o actualiza la existente.

        Cuando la curva ya existe, sus observaciones anteriores se sustituyen
        completamente por las observaciones de la entidad recibida.

        Args:
            star_candidate_id:
                Identificador interno del candidato.

            light_curve:
                Curva que debe persistirse.

        Returns:
            Tupla formada por:

            - Modelo insertado o actualizado.
            - True si se insertó una curva nueva.
            - False si se actualizó una curva existente.
        """

        self._validate_light_curve(light_curve)
        self._require_candidate(star_candidate_id)

        existing_model = self.get_by_identity(
            star_candidate_id=star_candidate_id,
            ztf_object_id=light_curve.ztf_object_id,
            band=light_curve.band,
            include_observations=True,
        )

        if existing_model is None:
            return (
                self.save(
                    star_candidate_id=star_candidate_id,
                    light_curve=light_curve,
                ),
                True,
            )

        existing_model.update_from_domain(light_curve)

        # La colección tiene delete-orphan, por lo que las observaciones
        # anteriores se eliminarán al hacer flush.
        existing_model.observations.clear()

        self._session.flush()

        existing_model.observations.extend(
            self._build_observation_models(light_curve)
        )

        existing_model.observation_count = len(
            existing_model.observations
        )

        self._session.flush()

        logger.debug(
            "Curva de luz actualizada. "
            "id=%s star_candidate_id=%s curve_key=%s observations=%d",
            existing_model.id,
            star_candidate_id,
            existing_model.curve_key,
            existing_model.observation_count,
        )

        return existing_model, False

    def save_many(
        self,
        *,
        star_candidate_id: int,
        light_curves: Iterable[LightCurve],
    ) -> SaveLightCurvesResult:
        """
        Inserta o actualiza varias curvas del mismo candidato.

        Args:
            star_candidate_id:
                Identificador del candidato al que pertenecen las curvas.

            light_curves:
                Colección de curvas que deben almacenarse.

        Returns:
            Resumen de la operación.
        """

        self._require_candidate(star_candidate_id)

        curve_list = self._materialize_light_curves(light_curves)

        inserted = 0
        updated = 0
        observations = 0

        for light_curve in curve_list:
            _, was_inserted = self.save_or_update(
                star_candidate_id=star_candidate_id,
                light_curve=light_curve,
            )

            observations += light_curve.observation_count

            if was_inserted:
                inserted += 1
            else:
                updated += 1

        result = SaveLightCurvesResult(
            processed=len(curve_list),
            inserted=inserted,
            updated=updated,
            observations=observations,
        )

        logger.info(
            "Curvas preparadas para persistencia. "
            "star_candidate_id=%s processed=%d inserted=%d "
            "updated=%d observations=%d",
            star_candidate_id,
            result.processed,
            result.inserted,
            result.updated,
            result.observations,
        )

        return result

    def delete(
        self,
        model: LightCurveModel,
    ) -> None:
        """
        Elimina una curva y sus observaciones.

        Args:
            model:
                Modelo que debe eliminarse.

        Raises:
            TypeError:
                Si el objeto no es LightCurveModel.
        """

        if not isinstance(model, LightCurveModel):
            raise TypeError(
                "model debe ser una instancia de LightCurveModel."
            )

        light_curve_id = model.id
        curve_key = model.curve_key

        self._session.delete(model)
        self._session.flush()

        logger.debug(
            "Curva de luz eliminada. id=%s curve_key=%s",
            light_curve_id,
            curve_key,
        )

    def delete_by_identity(
        self,
        *,
        star_candidate_id: int,
        ztf_object_id: int,
        band: PhotometricBand | str,
    ) -> bool:
        """
        Elimina una curva mediante su identidad lógica.

        Returns:
            True si se encontró y eliminó.
            False si la curva no existía.
        """

        model = self.get_by_identity(
            star_candidate_id=star_candidate_id,
            ztf_object_id=ztf_object_id,
            band=band,
            include_observations=False,
        )

        if model is None:
            return False

        self.delete(model)
        return True

    def _require_candidate(
        self,
        star_candidate_id: int,
    ) -> StarCandidateModel:
        """
        Comprueba que exista el candidato relacionado.

        Returns:
            Modelo del candidato.

        Raises:
            StarCandidateNotFoundError:
                Si el candidato no existe.
        """

        self._validate_positive_integer(
            star_candidate_id,
            field_name="star_candidate_id",
        )

        candidate = self._session.get(
            StarCandidateModel,
            star_candidate_id,
        )

        if candidate is None:
            raise StarCandidateNotFoundError(
                "No existe ningún candidato con "
                f"id={star_candidate_id}."
            )

        return candidate

    @staticmethod
    def _build_observation_models(
        light_curve: LightCurve,
    ) -> list[LightCurveObservationModel]:
        """
        Convierte las observaciones de dominio en modelos ORM.

        La clave foránea se asignará mediante la relación ORM con
        LightCurveModel.
        """

        return [
            LightCurveObservationModel.from_domain(observation)
            for observation in light_curve.observations
        ]

    @staticmethod
    def _materialize_light_curves(
        light_curves: Iterable[LightCurve],
    ) -> list[LightCurve]:
        """
        Materializa y valida una colección de curvas.
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
    def _validate_light_curve(
        light_curve: LightCurve,
    ) -> None:
        """
        Comprueba que el objeto sea una curva de dominio.
        """

        if not isinstance(light_curve, LightCurve):
            raise TypeError(
                "light_curve debe ser una instancia de LightCurve."
            )

    @staticmethod
    def _validate_positive_integer(
        value: int,
        *,
        field_name: str,
    ) -> None:
        """
        Valida un entero positivo.
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
        Valida un entero igual o superior a cero.
        """

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{field_name} debe ser un número entero."
            )

        if value < 0:
            raise ValueError(
                f"{field_name} no puede ser negativo."
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