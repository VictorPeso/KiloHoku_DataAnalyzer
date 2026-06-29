"""
Gestión básica del esquema de base de datos durante el desarrollo.

Este módulo permite crear y eliminar las tablas registradas en SQLAlchemy
sin utilizar todavía un sistema de migraciones.

Está pensado para las primeras fases del proyecto. Cuando el esquema se
estabilice, estas operaciones deberán sustituirse por migraciones Alembic.
"""

from __future__ import annotations

from etl.database.base import Base
from etl.database.models import StarCandidateModel
from etl.database.session import get_engine
from etl.logger import get_logger


logger = get_logger(__name__)


def create_database_schema() -> None:
    """
    Crea en PostgreSQL todas las tablas que todavía no existan.

    La operación no elimina tablas ni modifica las tablas existentes.
    """

    engine = get_engine()

    # Esta referencia asegura que StarCandidateModel haya sido importado
    # y registrado dentro de Base.metadata.
    _ = StarCandidateModel

    logger.info(
        "Iniciando creación del esquema de base de datos. tables=%s",
        sorted(Base.metadata.tables.keys()),
    )

    Base.metadata.create_all(
        bind=engine,
        checkfirst=True,
    )

    logger.info(
        "Esquema de base de datos creado o verificado correctamente."
    )


def drop_database_schema() -> None:
    """
    Elimina todas las tablas registradas en Base.metadata.

    Esta operación borra también todos los datos almacenados y solo debe
    utilizarse deliberadamente durante el desarrollo.
    """

    engine = get_engine()

    _ = StarCandidateModel

    logger.warning(
        "Iniciando eliminación completa del esquema. tables=%s",
        sorted(Base.metadata.tables.keys()),
    )

    Base.metadata.drop_all(
        bind=engine,
        checkfirst=True,
    )

    logger.warning(
        "Esquema de base de datos eliminado completamente."
    )


def recreate_database_schema() -> None:
    """
    Elimina y vuelve a crear todas las tablas.

    Todos los datos existentes serán eliminados.
    """

    logger.warning(
        "Recreando completamente el esquema de base de datos."
    )

    drop_database_schema()
    create_database_schema()

    logger.warning(
        "Esquema de base de datos recreado correctamente."
    )