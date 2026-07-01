"""
Modelo SQLAlchemy para observaciones individuales de curvas de luz ZTF.

Cada registro representa un punto fotométrico del VOTable descargado desde
NASA/IPAC.

La relación general es:

    star_candidates
        1 ─── N light_curves
                    1 ─── N light_curve_observations

Las observaciones pertenecen a una única curva mediante ``light_curve_id``.
Si se elimina la curva, sus observaciones se eliminan en cascada.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from etl.database.base import Base
from etl.domain.entities import LightCurveObservation


if TYPE_CHECKING:
    from etl.database.models.light_curve_model import LightCurveModel


class LightCurveObservationModel(Base):
    """
    Modelo ORM de una observación fotométrica ZTF.

    Cada instancia representa una fila del VOTable.

    La combinación:

        light_curve_id + exposure_id

    se utiliza como identidad lógica de una observación dentro de una curva.
    """

    __tablename__ = "light_curve_observations"

    __table_args__ = (
        UniqueConstraint(
            "light_curve_id",
            "exposure_id",
            name="uq_light_curve_observations_curve_exposure",
        ),
        CheckConstraint(
            "heliocentric_julian_date > 0",
            name="heliocentric_julian_date_positive",
        ),
        CheckConstraint(
            "modified_julian_date > 0",
            name="modified_julian_date_positive",
        ),
        CheckConstraint(
            "magnitude_error >= 0",
            name="magnitude_error_non_negative",
        ),
        CheckConstraint(
            "catalog_flags >= 0",
            name="catalog_flags_non_negative",
        ),
        CheckConstraint(
            "right_ascension >= 0 AND right_ascension < 360",
            name="right_ascension_range",
        ),
        CheckConstraint(
            "declination >= -90 AND declination <= 90",
            name="declination_range",
        ),
        CheckConstraint(
            "ccd_id IS NULL OR (ccd_id >= 1 AND ccd_id <= 16)",
            name="ccd_id_range",
        ),
        CheckConstraint(
            "quadrant_id IS NULL "
            "OR (quadrant_id >= 1 AND quadrant_id <= 4)",
            name="quadrant_id_range",
        ),
        CheckConstraint(
            "magnitude_zero_point_rms IS NULL "
            "OR magnitude_zero_point_rms >= 0",
            name="magnitude_zero_point_rms_non_negative",
        ),
        CheckConstraint(
            "color_coefficient_error IS NULL "
            "OR color_coefficient_error >= 0",
            name="color_coefficient_error_non_negative",
        ),
        CheckConstraint(
            "exposure_time IS NULL OR exposure_time >= 0",
            name="exposure_time_non_negative",
        ),
        CheckConstraint(
            "airmass IS NULL OR airmass >= 0",
            name="airmass_non_negative",
        ),
        Index(
            "ix_light_curve_observations_light_curve_id",
            "light_curve_id",
        ),
        Index(
            "ix_light_curve_observations_exposure_id",
            "exposure_id",
        ),
        Index(
            "ix_light_curve_observations_mjd",
            "modified_julian_date",
        ),
        Index(
            "ix_light_curve_observations_curve_mjd",
            "light_curve_id",
            "modified_julian_date",
        ),
        Index(
            "ix_light_curve_observations_catalog_flags",
            "catalog_flags",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    light_curve_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "light_curves.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    exposure_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    heliocentric_julian_date: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    modified_julian_date: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    magnitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    magnitude_error: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    catalog_flags: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    right_ascension: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    declination: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    chi: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    sharpness: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    file_fraction_day: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    field_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    ccd_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    quadrant_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    limiting_magnitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    magnitude_zero_point: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    magnitude_zero_point_rms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    color_coefficient: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    color_coefficient_error: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    exposure_time: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    airmass: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    program_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
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

    light_curve: Mapped[LightCurveModel] = relationship(
        back_populates="observations",
        passive_deletes=True,
    )

    @classmethod
    def from_domain(
        cls,
        observation: LightCurveObservation,
        *,
        light_curve_id: int | None = None,
    ) -> LightCurveObservationModel:
        """
        Crea un modelo ORM desde una observación de dominio.

        ``light_curve_id`` puede omitirse cuando el modelo se asociará
        mediante la relación ORM:

            light_curve_model.observations.append(observation_model)

        En ese caso, SQLAlchemy asignará la clave foránea al guardar el
        conjunto.

        Args:
            observation:
                Observación que debe convertirse.

            light_curve_id:
                Identificador de la curva relacionada. Puede ser None mientras
                el modelo todavía no se haya añadido a la sesión.

        Returns:
            Nuevo modelo ORM sin añadir a ninguna sesión.

        Raises:
            TypeError:
                Si ``observation`` no es LightCurveObservation o el
                identificador no es entero.

            ValueError:
                Si ``light_curve_id`` no es positivo.
        """

        if not isinstance(observation, LightCurveObservation):
            raise TypeError(
                "observation debe ser una instancia de "
                "LightCurveObservation."
            )

        if light_curve_id is not None:
            cls._validate_light_curve_id(light_curve_id)

        return cls(
            light_curve_id=light_curve_id,
            exposure_id=observation.exposure_id,
            heliocentric_julian_date=(
                observation.heliocentric_julian_date
            ),
            modified_julian_date=observation.modified_julian_date,
            magnitude=observation.magnitude,
            magnitude_error=observation.magnitude_error,
            catalog_flags=observation.catalog_flags,
            right_ascension=observation.right_ascension,
            declination=observation.declination,
            chi=observation.chi,
            sharpness=observation.sharpness,
            file_fraction_day=observation.file_fraction_day,
            field_id=observation.field_id,
            ccd_id=observation.ccd_id,
            quadrant_id=observation.quadrant_id,
            limiting_magnitude=observation.limiting_magnitude,
            magnitude_zero_point=observation.magnitude_zero_point,
            magnitude_zero_point_rms=(
                observation.magnitude_zero_point_rms
            ),
            color_coefficient=observation.color_coefficient,
            color_coefficient_error=(
                observation.color_coefficient_error
            ),
            exposure_time=observation.exposure_time,
            airmass=observation.airmass,
            program_id=observation.program_id,
        )

    def to_domain(self) -> LightCurveObservation:
        """
        Convierte el modelo ORM en una observación de dominio.

        Returns:
            Nueva instancia de LightCurveObservation.
        """

        return LightCurveObservation(
            exposure_id=self.exposure_id,
            heliocentric_julian_date=(
                self.heliocentric_julian_date
            ),
            modified_julian_date=self.modified_julian_date,
            magnitude=self.magnitude,
            magnitude_error=self.magnitude_error,
            catalog_flags=self.catalog_flags,
            right_ascension=self.right_ascension,
            declination=self.declination,
            chi=self.chi,
            sharpness=self.sharpness,
            file_fraction_day=self.file_fraction_day,
            field_id=self.field_id,
            ccd_id=self.ccd_id,
            quadrant_id=self.quadrant_id,
            limiting_magnitude=self.limiting_magnitude,
            magnitude_zero_point=self.magnitude_zero_point,
            magnitude_zero_point_rms=(
                self.magnitude_zero_point_rms
            ),
            color_coefficient=self.color_coefficient,
            color_coefficient_error=(
                self.color_coefficient_error
            ),
            exposure_time=self.exposure_time,
            airmass=self.airmass,
            program_id=self.program_id,
        )

    def update_from_domain(
        self,
        observation: LightCurveObservation,
    ) -> None:
        """
        Actualiza el modelo desde una observación de dominio.

        No permite modificar ``exposure_id``, ya que forma parte de la
        identidad lógica de la observación dentro de la curva.

        Args:
            observation:
                Observación con los valores actualizados.

        Raises:
            TypeError:
                Si el objeto no es LightCurveObservation.

            ValueError:
                Si el identificador de exposición no coincide.
        """

        if not isinstance(observation, LightCurveObservation):
            raise TypeError(
                "observation debe ser una instancia de "
                "LightCurveObservation."
            )

        if observation.exposure_id != self.exposure_id:
            raise ValueError(
                "No se puede actualizar una observación utilizando un "
                "exposure_id diferente. "
                f"Modelo: {self.exposure_id}. "
                f"Entidad: {observation.exposure_id}."
            )

        self.heliocentric_julian_date = (
            observation.heliocentric_julian_date
        )
        self.modified_julian_date = observation.modified_julian_date

        self.magnitude = observation.magnitude
        self.magnitude_error = observation.magnitude_error
        self.catalog_flags = observation.catalog_flags

        self.right_ascension = observation.right_ascension
        self.declination = observation.declination

        self.chi = observation.chi
        self.sharpness = observation.sharpness

        self.file_fraction_day = observation.file_fraction_day
        self.field_id = observation.field_id
        self.ccd_id = observation.ccd_id
        self.quadrant_id = observation.quadrant_id

        self.limiting_magnitude = observation.limiting_magnitude
        self.magnitude_zero_point = observation.magnitude_zero_point
        self.magnitude_zero_point_rms = (
            observation.magnitude_zero_point_rms
        )

        self.color_coefficient = observation.color_coefficient
        self.color_coefficient_error = (
            observation.color_coefficient_error
        )

        self.exposure_time = observation.exposure_time
        self.airmass = observation.airmass
        self.program_id = observation.program_id

    @property
    def has_quality_flags(self) -> bool:
        """
        Indica si la observación tiene flags de catálogo.
        """

        return self.catalog_flags != 0

    @property
    def is_unflagged(self) -> bool:
        """
        Indica si la observación no tiene flags de catálogo.
        """

        return self.catalog_flags == 0

    @staticmethod
    def _validate_light_curve_id(
        light_curve_id: int,
    ) -> None:
        """
        Valida la clave primaria de una curva de luz.
        """

        if (
            isinstance(light_curve_id, bool)
            or not isinstance(light_curve_id, int)
        ):
            raise TypeError(
                "light_curve_id debe ser un número entero."
            )

        if light_curve_id <= 0:
            raise ValueError(
                "light_curve_id debe ser mayor que cero."
            )