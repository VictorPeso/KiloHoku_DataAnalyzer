"""
Modelo SQLAlchemy para candidatos estelares.

Este módulo define la representación persistente de la entidad
StarCandidate dentro de PostgreSQL.

La entidad de dominio y el modelo ORM están separados deliberadamente:

    StarCandidate
        Representa el candidato dentro de la lógica de la aplicación.

    StarCandidateModel
        Representa la fila almacenada en la base de datos.

El modelo también proporciona métodos para convertir entre ambas
representaciones.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from etl.database.base import Base
from etl.domain.entities import StarCandidate


MAX_ALERT_URL_LENGTH: Final[int] = 2048
MAX_SIMBAD_TARGET_LENGTH: Final[int] = 2048
MAX_GAIA_DR3_NAME_LENGTH: Final[int] = 128
MAX_OBJECT_CLASS_LENGTH: Final[int] = 128
MAX_RESOURCE_URL_LENGTH: Final[int] = 2048


class StarCandidateModel(Base):
    """
    Modelo ORM de un candidato estelar.

    Cada instancia representa una fila de la tabla ``star_candidates``.

    La clave primaria interna ``id`` se utiliza únicamente dentro de la base
    de datos. La alerta astronómica se identifica externamente mediante
    ``alert_url`` y la propiedad derivada ``alert_id`` de la entidad.
    """

    __tablename__ = "star_candidates"

    __table_args__ = (
        UniqueConstraint(
            "alert_url",
            name="alert_url",
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
            "angular_distance IS NULL OR angular_distance >= 0",
            name="angular_distance_non_negative",
        ),
        CheckConstraint(
            "parallax_error >= 0",
            name="parallax_error_non_negative",
        ),
        Index(
            "ix_star_candidates_observation_date",
            "observation_date",
        ),
        Index(
            "ix_star_candidates_gaia_dr3_name",
            "gaia_dr3_name",
        ),
        Index(
            "ix_star_candidates_coordinates",
            "right_ascension",
            "declination",
        ),
        Index(
            "ix_star_candidates_object_class",
            "object_class",
        ),
        Index(
            "ix_star_candidates_processing_flags",
            "is_in_white_dwarf_zone",
            "has_spectrum",
            "has_emission",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    alert_url: Mapped[str] = mapped_column(
        String(MAX_ALERT_URL_LENGTH),
        nullable=False,
    )

    observation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
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

    closest_simbad_target: Mapped[str | None] = mapped_column(
        String(MAX_SIMBAD_TARGET_LENGTH),
        nullable=True,
    )

    object_class: Mapped[str | None] = mapped_column(
        String(MAX_OBJECT_CLASS_LENGTH),
        nullable=True,
    )

    angular_distance: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    gaia_dr3_name: Mapped[str] = mapped_column(
        String(MAX_GAIA_DR3_NAME_LENGTH),
        nullable=False,
    )

    gaia_g_magnitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    gaia_bp_magnitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    gaia_rp_magnitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    parallax: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    parallax_error: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    is_in_white_dwarf_zone: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    has_spectrum: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    has_emission: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    data_file_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    plot_url: Mapped[str | None] = mapped_column(
        Text,
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

    @classmethod
    def from_domain(
        cls,
        candidate: StarCandidate,
    ) -> StarCandidateModel:
        """
        Crea un modelo ORM a partir de una entidad de dominio.

        Este método no añade el modelo a ninguna sesión ni ejecuta ninguna
        consulta. Únicamente realiza la conversión de datos.

        Args:
            candidate:
                Entidad StarCandidate que debe convertirse.

        Returns:
            Nueva instancia de StarCandidateModel.

        Raises:
            TypeError:
                Si el objeto recibido no es StarCandidate.
        """

        if not isinstance(candidate, StarCandidate):
            raise TypeError(
                "candidate debe ser una instancia de StarCandidate."
            )

        return cls(
            alert_url=candidate.alert_url,
            observation_date=candidate.observation_date,
            right_ascension=candidate.right_ascension,
            declination=candidate.declination,
            closest_simbad_target=(
                candidate.closest_simbad_target
            ),
            object_class=candidate.object_class,
            angular_distance=candidate.angular_distance,
            gaia_dr3_name=candidate.gaia_dr3_name,
            gaia_g_magnitude=candidate.gaia_g_magnitude,
            gaia_bp_magnitude=candidate.gaia_bp_magnitude,
            gaia_rp_magnitude=candidate.gaia_rp_magnitude,
            parallax=candidate.parallax,
            parallax_error=candidate.parallax_error,
            is_in_white_dwarf_zone=(
                candidate.is_in_white_dwarf_zone
            ),
            has_spectrum=candidate.has_spectrum,
            has_emission=candidate.has_emission,
            data_file_url=candidate.data_file_url,
            plot_url=candidate.plot_url,
        )

    def to_domain(self) -> StarCandidate:
        """
        Convierte el modelo ORM en una entidad de dominio.

        Returns:
            Nueva entidad StarCandidate con los datos almacenados en el
            modelo.
        """

        return StarCandidate(
            alert_url=self.alert_url,
            observation_date=self.observation_date,
            right_ascension=self.right_ascension,
            declination=self.declination,
            closest_simbad_target=self.closest_simbad_target,
            object_class=self.object_class,
            angular_distance=self.angular_distance,
            gaia_dr3_name=self.gaia_dr3_name,
            gaia_g_magnitude=self.gaia_g_magnitude,
            gaia_bp_magnitude=self.gaia_bp_magnitude,
            gaia_rp_magnitude=self.gaia_rp_magnitude,
            parallax=self.parallax,
            parallax_error=self.parallax_error,
            is_in_white_dwarf_zone=self.is_in_white_dwarf_zone,
            has_spectrum=self.has_spectrum,
            has_emission=self.has_emission,
            data_file_url=self.data_file_url,
            plot_url=self.plot_url,
        )

    def update_from_domain(
        self,
        candidate: StarCandidate,
    ) -> None:
        """
        Actualiza el modelo ORM usando una entidad de dominio.

        Este método resulta útil cuando ya existe un registro para la misma
        alerta y se desean actualizar sus datos durante una nueva importación.

        No ejecuta commit. La confirmación de la transacción corresponde a
        ``session_scope``.

        Args:
            candidate:
                Entidad con los nuevos valores.

        Raises:
            TypeError:
                Si el objeto recibido no es StarCandidate.

            ValueError:
                Si la entidad pertenece a una alerta diferente.
        """

        if not isinstance(candidate, StarCandidate):
            raise TypeError(
                "candidate debe ser una instancia de StarCandidate."
            )

        if candidate.alert_url != self.alert_url:
            raise ValueError(
                "No se puede actualizar un modelo con una alerta diferente. "
                f"Modelo: {self.alert_url!r}. "
                f"Entidad: {candidate.alert_url!r}."
            )

        self.observation_date = candidate.observation_date
        self.right_ascension = candidate.right_ascension
        self.declination = candidate.declination

        self.closest_simbad_target = (
            candidate.closest_simbad_target
        )
        self.object_class = candidate.object_class
        self.angular_distance = candidate.angular_distance

        self.gaia_dr3_name = candidate.gaia_dr3_name
        self.gaia_g_magnitude = candidate.gaia_g_magnitude
        self.gaia_bp_magnitude = candidate.gaia_bp_magnitude
        self.gaia_rp_magnitude = candidate.gaia_rp_magnitude
        self.parallax = candidate.parallax
        self.parallax_error = candidate.parallax_error

        self.is_in_white_dwarf_zone = (
            candidate.is_in_white_dwarf_zone
        )
        self.has_spectrum = candidate.has_spectrum
        self.has_emission = candidate.has_emission

        self.data_file_url = candidate.data_file_url
        self.plot_url = candidate.plot_url

    @property
    def alert_id(self) -> str:
        """
        Obtiene el identificador de alerta a partir de ``alert_url``.

        Returns:
            Parte final de la URL de alerta.
        """

        return self.alert_url.rstrip("/").rsplit("/", maxsplit=1)[-1]