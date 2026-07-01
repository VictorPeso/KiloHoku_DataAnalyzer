"""
Modelo SQLAlchemy para curvas de luz ZTF.

Cada registro representa una curva correspondiente a:

    candidato + objeto ZTF + banda fotométrica

Las observaciones individuales se almacenan en la tabla
``light_curve_observations`` y se relacionan mediante ``light_curve_id``.

La relación general es:

    star_candidates
        1 ─── N light_curves
                    1 ─── N light_curve_observations
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Final

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from etl.database.base import Base
from etl.domain.entities import LightCurve
from etl.domain.value_objects import PhotometricBand


if TYPE_CHECKING:
    from etl.database.models.light_curve_observation_model import (
        LightCurveObservationModel,
    )
    from etl.database.models.star_candidate_model import (
        StarCandidateModel,
    )


MAX_BAND_LENGTH: Final[int] = 1
MAX_SOURCE_COLLECTION_LENGTH: Final[int] = 128


class LightCurveModel(Base):
    """
    Modelo ORM de una curva de luz ZTF.

    Una consulta posicional puede encontrar más de un objeto ZTF dentro del
    radio de búsqueda. Por ello, un mismo candidato puede tener varias curvas
    para una misma banda, siempre que tengan distinto ``ztf_object_id``.

    La identidad lógica de una curva queda determinada por:

        star_candidate_id + ztf_object_id + band
    """

    __tablename__ = "light_curves"

    __table_args__ = (
        UniqueConstraint(
            "star_candidate_id",
            "ztf_object_id",
            "band",
            name="uq_light_curves_candidate_object_band",
        ),
        CheckConstraint(
            "band IN ('g', 'r', 'i')",
            name="band_supported",
        ),
        CheckConstraint(
            "source_right_ascension >= 0 "
            "AND source_right_ascension < 360",
            name="source_right_ascension_range",
        ),
        CheckConstraint(
            "source_declination >= -90 "
            "AND source_declination <= 90",
            name="source_declination_range",
        ),
        CheckConstraint(
            "search_right_ascension >= 0 "
            "AND search_right_ascension < 360",
            name="search_right_ascension_range",
        ),
        CheckConstraint(
            "search_declination >= -90 "
            "AND search_declination <= 90",
            name="search_declination_range",
        ),
        CheckConstraint(
            "search_radius_degrees > 0",
            name="search_radius_positive",
        ),
        CheckConstraint(
            "observation_count >= 0",
            name="observation_count_non_negative",
        ),
        Index(
            "ix_light_curves_star_candidate_id",
            "star_candidate_id",
        ),
        Index(
            "ix_light_curves_ztf_object_id",
            "ztf_object_id",
        ),
        Index(
            "ix_light_curves_band",
            "band",
        ),
        Index(
            "ix_light_curves_candidate_band",
            "star_candidate_id",
            "band",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    star_candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "star_candidates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    ztf_object_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    band: Mapped[str] = mapped_column(
        String(MAX_BAND_LENGTH),
        nullable=False,
    )

    source_right_ascension: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    source_declination: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    search_right_ascension: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    search_declination: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    search_radius_degrees: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    source_collection: Mapped[str] = mapped_column(
        String(MAX_SOURCE_COLLECTION_LENGTH),
        nullable=False,
        default="NASA/IPAC ZTF",
        server_default="NASA/IPAC ZTF",
    )

    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    candidate: Mapped[StarCandidateModel] = relationship(
        lazy="joined",
        passive_deletes=True,
    )

    observations: Mapped[list[LightCurveObservationModel]] = relationship(
        back_populates="light_curve",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by=(
            "LightCurveObservationModel.modified_julian_date, "
            "LightCurveObservationModel.exposure_id"
        ),
    )

    @classmethod
    def from_domain(
        cls,
        light_curve: LightCurve,
        *,
        star_candidate_id: int,
    ) -> LightCurveModel:
        """
        Crea un modelo ORM a partir de una entidad de dominio.

        Este método crea únicamente el registro padre de la curva. Las
        observaciones se convertirán y asociarán desde el repositorio cuando
        exista ``LightCurveObservationModel``.

        Args:
            light_curve:
                Curva de luz que debe almacenarse.

            star_candidate_id:
                Clave primaria del candidato al que pertenece la curva.

        Returns:
            Modelo ORM sin añadir todavía a una sesión.

        Raises:
            TypeError:
                Si ``light_curve`` no es una instancia de LightCurve o si
                ``star_candidate_id`` no es entero.

            ValueError:
                Si ``star_candidate_id`` no es positivo.
        """

        if not isinstance(light_curve, LightCurve):
            raise TypeError(
                "light_curve debe ser una instancia de LightCurve."
            )

        cls._validate_star_candidate_id(star_candidate_id)

        return cls(
            star_candidate_id=star_candidate_id,
            ztf_object_id=light_curve.ztf_object_id,
            band=light_curve.band.value,
            source_right_ascension=(
                light_curve.source_right_ascension
            ),
            source_declination=light_curve.source_declination,
            search_right_ascension=(
                light_curve.search_right_ascension
            ),
            search_declination=light_curve.search_declination,
            search_radius_degrees=(
                light_curve.search_radius_degrees
            ),
            observation_count=light_curve.observation_count,
            source_collection=light_curve.source_collection,
        )

    def update_from_domain(
        self,
        light_curve: LightCurve,
    ) -> None:
        """
        Actualiza los metadatos de la curva desde el dominio.

        No permite modificar:

        - El candidato relacionado.
        - El identificador del objeto ZTF.
        - La banda fotométrica.

        Esos tres campos forman la identidad lógica de la curva.

        Args:
            light_curve:
                Entidad con los valores actualizados.

        Raises:
            TypeError:
                Si el valor no es una instancia de LightCurve.

            ValueError:
                Si el objeto ZTF o la banda no coinciden.
        """

        if not isinstance(light_curve, LightCurve):
            raise TypeError(
                "light_curve debe ser una instancia de LightCurve."
            )

        if light_curve.ztf_object_id != self.ztf_object_id:
            raise ValueError(
                "No se puede actualizar la curva utilizando un "
                "ztf_object_id diferente. "
                f"Modelo: {self.ztf_object_id}. "
                f"Entidad: {light_curve.ztf_object_id}."
            )

        current_band = PhotometricBand.from_value(self.band)

        if light_curve.band != current_band:
            raise ValueError(
                "No se puede actualizar la curva utilizando una banda "
                "diferente. "
                f"Modelo: {current_band.value!r}. "
                f"Entidad: {light_curve.band.value!r}."
            )

        self.source_right_ascension = (
            light_curve.source_right_ascension
        )
        self.source_declination = light_curve.source_declination

        self.search_right_ascension = (
            light_curve.search_right_ascension
        )
        self.search_declination = light_curve.search_declination
        self.search_radius_degrees = (
            light_curve.search_radius_degrees
        )

        self.observation_count = light_curve.observation_count
        self.source_collection = light_curve.source_collection

        # Indica cuándo se obtuvo por última vez la información de la API.
        self.downloaded_at = func.now()

    @property
    def photometric_band(self) -> PhotometricBand:
        """
        Devuelve la banda almacenada como PhotometricBand.
        """

        return PhotometricBand.from_value(self.band)

    @property
    def curve_key(self) -> str:
        """
        Devuelve una clave legible para identificar la curva.

        Ejemplo:

            458116300003161:g
        """

        return f"{self.ztf_object_id}:{self.band}"

    @property
    def candidate_curve_key(self) -> str:
        """
        Devuelve una clave que incluye al candidato relacionado.

        Ejemplo:

            25:458116300003161:g
        """

        return (
            f"{self.star_candidate_id}:"
            f"{self.ztf_object_id}:"
            f"{self.band}"
        )

    @staticmethod
    def _validate_star_candidate_id(
        star_candidate_id: int,
    ) -> None:
        """
        Valida la clave primaria de un candidato.
        """

        if (
            isinstance(star_candidate_id, bool)
            or not isinstance(star_candidate_id, int)
        ):
            raise TypeError(
                "star_candidate_id debe ser un número entero."
            )

        if star_candidate_id <= 0:
            raise ValueError(
                "star_candidate_id debe ser mayor que cero."
            )