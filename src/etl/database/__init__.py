"""
Infraestructura de acceso a la base de datos.
"""

from etl.database.base import Base, metadata
from etl.database.session import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    check_database_connection,
    create_session,
    dispose_engine,
    get_engine,
    get_session_factory,
    read_only_session_scope,
    session_scope,
)
from etl.database.schema import (
    create_database_schema,
    drop_database_schema,
    recreate_database_schema,
)

__all__ = [
    "Base",
    "metadata",
    "create_database_schema",
    "drop_database_schema",
    "recreate_database_schema",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "check_database_connection",
    "create_session",
    "dispose_engine",
    "get_engine",
    "get_session_factory",
    "read_only_session_scope",
    "session_scope",
]