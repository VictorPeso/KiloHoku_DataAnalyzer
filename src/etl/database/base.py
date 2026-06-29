"""
Base declarativa común para los modelos SQLAlchemy.

Todos los modelos ORM de la aplicación deben heredar de ``Base``.

Este módulo centraliza:

- El registro de tablas mediante SQLAlchemy MetaData.
- La convención de nombres de índices y restricciones.
- La clase base declarativa utilizada por todos los modelos.
- La representación básica de los objetos ORM.

La clase Base no crea tablas ni establece conexiones con PostgreSQL.
Su única responsabilidad es servir como fundamento común para los modelos.

Las tablas se crearán y modificarán mediante migraciones de Alembic.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}
"""
Convención de nombres aplicada a restricciones e índices.

Significado de cada clave:

    ix:
        Índices.

    uq:
        Restricciones UNIQUE.

    ck:
        Restricciones CHECK.

    fk:
        Claves foráneas.

    pk:
        Claves primarias.

Ejemplos de nombres generados:

    pk_star_candidates
    uq_star_candidates_alert_id
    ix_star_candidates_observation_date
    fk_light_curves_star_candidate_id_star_candidates
"""


metadata = MetaData(
    naming_convention=NAMING_CONVENTION,
)
"""
Registro común de todas las tablas ORM.

Cada modelo que herede de Base añadirá su tabla a este objeto.
Alembic utilizará posteriormente ``Base.metadata`` para detectar cambios
entre los modelos y el esquema real de PostgreSQL.
"""


class Base(DeclarativeBase):
    """
    Clase base declarativa de todos los modelos SQLAlchemy.

    Ejemplo:

        class StarCandidateModel(Base):
            __tablename__ = "star_candidates"

            ...

    Attributes:
        metadata:
            Registro compartido de tablas y restricciones.
    """

    metadata = metadata

    def __repr__(self) -> str:
        """
        Devuelve una representación segura y breve del objeto ORM.

        Solo incluye la clase y la clave primaria conocida por SQLAlchemy.
        No muestra automáticamente todos los atributos, evitando incluir
        accidentalmente grandes cantidades de datos o información sensible.
        """

        identity = self._get_identity_representation()

        return (
            f"<{type(self).__name__}"
            f"{f' {identity}' if identity else ''}>"
        )

    def _get_identity_representation(self) -> str | None:
        """
        Obtiene una representación de la clave primaria del objeto.

        Returns:
            Texto con las columnas de clave primaria y sus valores, o None
            cuando el modelo aún no dispone de identidad.
        """

        table = getattr(type(self), "__table__", None)

        if table is None:
            return None

        identity_parts: list[str] = []

        for primary_key_column in table.primary_key.columns:
            attribute_name = primary_key_column.key

            value: Any = getattr(
                self,
                attribute_name,
                None,
            )

            if value is not None:
                identity_parts.append(
                    f"{attribute_name}={value!r}"
                )

        if not identity_parts:
            return None

        return " ".join(identity_parts)