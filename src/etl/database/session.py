"""
Configuración centralizada de SQLAlchemy y gestión de sesiones.

Este módulo se encarga de:

- Leer la configuración de PostgreSQL desde variables de entorno.
- Crear un único Engine compartido por la aplicación.
- Configurar el pool de conexiones.
- Crear sesiones SQLAlchemy.
- Gestionar commits, rollbacks y cierres de sesión.
- Comprobar la conectividad con la base de datos.
- Cerrar el pool de conexiones durante el apagado de la aplicación.

Los repositorios y loaders deben solicitar sesiones mediante las funciones
de este módulo. No deben crear engines ni conexiones por su cuenta.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Final

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

# La importación de settings garantiza que el archivo .env haya sido cargado
# antes de leer las variables relacionadas con la base de datos.
from etl.config import settings
from etl.logger import get_logger


logger = get_logger(__name__)


DEFAULT_POOL_SIZE: Final[int] = 5
DEFAULT_MAX_OVERFLOW: Final[int] = 10
DEFAULT_POOL_TIMEOUT: Final[int] = 30
DEFAULT_POOL_RECYCLE: Final[int] = 1800
DEFAULT_POOL_PRE_PING: Final[bool] = True
DEFAULT_DATABASE_ECHO: Final[bool] = False

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

# Protege la inicialización del Engine si varios hilos intentan obtenerlo
# simultáneamente durante el arranque.
_initialization_lock = Lock()


class DatabaseConfigurationError(RuntimeError):
    """
    Error producido por una configuración inválida de la base de datos.
    """


class DatabaseConnectionError(RuntimeError):
    """
    Error producido cuando no se puede conectar con la base de datos.
    """


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """
    Configuración de conexión y del pool de SQLAlchemy.

    Attributes:
        url:
            URL completa de conexión a PostgreSQL.

        pool_size:
            Número de conexiones permanentes mantenidas en el pool.

        max_overflow:
            Número máximo de conexiones adicionales que SQLAlchemy puede
            abrir cuando el pool permanente está ocupado.

        pool_timeout:
            Segundos máximos durante los que se espera una conexión libre.

        pool_recycle:
            Segundos tras los cuales una conexión se considera antigua y se
            sustituye antes de volver a utilizarla.

        pool_pre_ping:
            Indica si SQLAlchemy debe comprobar las conexiones antes de
            entregarlas a la aplicación.

        echo:
            Indica si SQLAlchemy debe registrar las sentencias SQL.
    """

    url: URL
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool
    echo: bool

    @property
    def safe_url(self) -> str:
        """
        Devuelve la URL ocultando la contraseña.

        Esta representación es la única que debe escribirse en los logs.
        """

        return self.url.render_as_string(
            hide_password=True,
        )


def _get_required_environment_variable(
    variable_name: str,
) -> str:
    """
    Obtiene una variable de entorno obligatoria.

    Args:
        variable_name:
            Nombre de la variable.

    Returns:
        Valor sin espacios exteriores.

    Raises:
        DatabaseConfigurationError:
            Si la variable no existe o está vacía.
    """

    value = os.getenv(variable_name)

    if value is None or not value.strip():
        raise DatabaseConfigurationError(
            f"La variable de entorno {variable_name} es obligatoria."
        )

    return value.strip()


def _get_integer_environment_variable(
    variable_name: str,
    *,
    default: int,
    minimum: int,
) -> int:
    """
    Obtiene y valida una variable de entorno entera.

    Args:
        variable_name:
            Nombre de la variable.

        default:
            Valor utilizado cuando no está definida.

        minimum:
            Valor mínimo permitido.

    Returns:
        Entero validado.

    Raises:
        DatabaseConfigurationError:
            Si el valor no es un entero o es inferior al mínimo.
    """

    raw_value = os.getenv(
        variable_name,
        str(default),
    ).strip()

    try:
        parsed_value = int(raw_value)
    except ValueError as error:
        raise DatabaseConfigurationError(
            f"{variable_name} debe contener un número entero. "
            f"Valor recibido: {raw_value!r}."
        ) from error

    if parsed_value < minimum:
        raise DatabaseConfigurationError(
            f"{variable_name} debe ser igual o superior a {minimum}. "
            f"Valor recibido: {parsed_value}."
        )

    return parsed_value


def _get_boolean_environment_variable(
    variable_name: str,
    *,
    default: bool,
) -> bool:
    """
    Obtiene y valida una variable de entorno booleana.

    Valores verdaderos admitidos:

        true, 1, yes, y, on

    Valores falsos admitidos:

        false, 0, no, n, off
    """

    raw_value = os.getenv(variable_name)

    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()

    true_values = {
        "true",
        "1",
        "yes",
        "y",
        "on",
    }

    false_values = {
        "false",
        "0",
        "no",
        "n",
        "off",
    }

    if normalized_value in true_values:
        return True

    if normalized_value in false_values:
        return False

    raise DatabaseConfigurationError(
        f"{variable_name} debe contener un valor booleano válido. "
        f"Valor recibido: {raw_value!r}."
    )


def _load_database_settings() -> DatabaseSettings:
    """
    Carga y valida la configuración de PostgreSQL.

    Returns:
        Configuración validada.

    Raises:
        DatabaseConfigurationError:
            Si la URL o alguna opción del pool es inválida.
    """

    raw_database_url = _get_required_environment_variable(
        "DATABASE_URL"
    )

    try:
        database_url = make_url(raw_database_url)
    except Exception as error:
        raise DatabaseConfigurationError(
            "DATABASE_URL no contiene una URL de conexión válida."
        ) from error

    if database_url.get_backend_name() != "postgresql":
        raise DatabaseConfigurationError(
            "DATABASE_URL debe utilizar PostgreSQL. "
            f"Backend recibido: {database_url.get_backend_name()!r}."
        )

    driver_name = database_url.get_driver_name()

    if driver_name != "psycopg":
        raise DatabaseConfigurationError(
            "DATABASE_URL debe utilizar el driver psycopg. "
            "El esquema esperado comienza por "
            "'postgresql+psycopg://'. "
            f"Driver recibido: {driver_name!r}."
        )

    if not database_url.database:
        raise DatabaseConfigurationError(
            "DATABASE_URL debe indicar el nombre de la base de datos."
        )

    return DatabaseSettings(
        url=database_url,
        pool_size=_get_integer_environment_variable(
            "DATABASE_POOL_SIZE",
            default=DEFAULT_POOL_SIZE,
            minimum=1,
        ),
        max_overflow=_get_integer_environment_variable(
            "DATABASE_MAX_OVERFLOW",
            default=DEFAULT_MAX_OVERFLOW,
            minimum=0,
        ),
        pool_timeout=_get_integer_environment_variable(
            "DATABASE_POOL_TIMEOUT",
            default=DEFAULT_POOL_TIMEOUT,
            minimum=1,
        ),
        pool_recycle=_get_integer_environment_variable(
            "DATABASE_POOL_RECYCLE",
            default=DEFAULT_POOL_RECYCLE,
            minimum=0,
        ),
        pool_pre_ping=_get_boolean_environment_variable(
            "DATABASE_POOL_PRE_PING",
            default=DEFAULT_POOL_PRE_PING,
        ),
        echo=_get_boolean_environment_variable(
            "DATABASE_ECHO",
            default=DEFAULT_DATABASE_ECHO,
        ),
    )


def get_engine() -> Engine:
    """
    Obtiene el Engine compartido de SQLAlchemy.

    El Engine se crea de forma perezosa la primera vez que se solicita.
    Crear el objeto Engine no abre necesariamente una conexión inmediata;
    las conexiones se obtienen del pool cuando se ejecuta una operación.

    Returns:
        Engine configurado.

    Raises:
        DatabaseConfigurationError:
            Si la configuración es inválida.
    """

    global _engine
    global _session_factory

    if _engine is not None:
        return _engine

    with _initialization_lock:
        # Se comprueba de nuevo dentro del lock por si otro hilo creó el
        # Engine mientras este hilo esperaba.
        if _engine is not None:
            return _engine

        database_settings = _load_database_settings()

        logger.info(
            "Inicializando Engine de SQLAlchemy. "
            "database_url=%s pool_size=%d max_overflow=%d "
            "pool_timeout=%d pool_recycle=%d pool_pre_ping=%s "
            "echo=%s environment=%s",
            database_settings.safe_url,
            database_settings.pool_size,
            database_settings.max_overflow,
            database_settings.pool_timeout,
            database_settings.pool_recycle,
            database_settings.pool_pre_ping,
            database_settings.echo,
            settings.app_environment,
        )

        try:
            engine = create_engine(
                database_settings.url,
                pool_size=database_settings.pool_size,
                max_overflow=database_settings.max_overflow,
                pool_timeout=database_settings.pool_timeout,
                pool_recycle=database_settings.pool_recycle,
                pool_pre_ping=database_settings.pool_pre_ping,
                echo=database_settings.echo,
            )
        except (SQLAlchemyError, TypeError, ValueError) as error:
            logger.exception(
                "No se pudo inicializar el Engine de SQLAlchemy. "
                "database_url=%s",
                database_settings.safe_url,
            )

            raise DatabaseConfigurationError(
                "No se pudo inicializar el Engine de SQLAlchemy."
            ) from error

        factory = sessionmaker(
            bind=engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

        _engine = engine
        _session_factory = factory

        logger.info(
            "Engine y fábrica de sesiones inicializados correctamente. "
            "database_url=%s",
            database_settings.safe_url,
        )

        return _engine


def get_session_factory() -> sessionmaker[Session]:
    """
    Obtiene la fábrica compartida de sesiones.

    Returns:
        sessionmaker configurado para el Engine de la aplicación.
    """

    global _session_factory

    if _session_factory is None:
        get_engine()

    if _session_factory is None:
        # Esta comprobación permite que el analizador de tipos comprenda que
        # la función nunca devuelve None.
        raise RuntimeError(
            "La fábrica de sesiones no pudo inicializarse."
        )

    return _session_factory


def create_session() -> Session:
    """
    Crea una nueva sesión de SQLAlchemy.

    La función que invoque este método será responsable de cerrar la sesión.
    En la mayoría de los casos debe preferirse ``session_scope()``.

    Returns:
        Nueva sesión asociada al Engine de la aplicación.
    """

    session_factory = get_session_factory()
    return session_factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Proporciona una sesión con gestión automática de la transacción.

    Comportamiento:

    - Crea una sesión.
    - Entrega la sesión al bloque ``with``.
    - Ejecuta ``commit`` si el bloque termina correctamente.
    - Ejecuta ``rollback`` si se produce una excepción.
    - Cierra siempre la sesión.

    Ejemplo:

        with session_scope() as session:
            repository = StarCandidateRepository(session)
            repository.save(candidate)

    Yields:
        Sesión activa de SQLAlchemy.

    Raises:
        SQLAlchemyError:
            Si falla una operación de base de datos.

        Exception:
            Propaga cualquier excepción producida dentro del bloque.
    """

    session = create_session()

    logger.debug(
        "Sesión de base de datos creada. session_id=%s",
        id(session),
    )

    try:
        yield session
        session.commit()

        logger.debug(
            "Transacción confirmada. session_id=%s",
            id(session),
        )

    except Exception:
        session.rollback()

        logger.exception(
            "La transacción ha fallado y se ha ejecutado rollback. "
            "session_id=%s",
            id(session),
        )

        raise

    finally:
        session.close()

        logger.debug(
            "Sesión de base de datos cerrada. session_id=%s",
            id(session),
        )


@contextmanager
def read_only_session_scope() -> Generator[Session, None, None]:
    """
    Proporciona una sesión destinada a operaciones de lectura.

    No realiza commit. Al finalizar se ejecuta rollback para cerrar cualquier
    transacción implícita iniciada por SQLAlchemy y posteriormente se cierra
    la sesión.

    Yields:
        Sesión activa para consultas.
    """

    session = create_session()

    logger.debug(
        "Sesión de lectura creada. session_id=%s",
        id(session),
    )

    try:
        yield session

    except Exception:
        logger.exception(
            "La sesión de lectura ha finalizado con un error. "
            "session_id=%s",
            id(session),
        )
        raise

    finally:
        session.rollback()
        session.close()

        logger.debug(
            "Sesión de lectura cerrada. session_id=%s",
            id(session),
        )


def check_database_connection() -> None:
    """
    Comprueba que la aplicación puede conectarse a PostgreSQL.

    Ejecuta una consulta mínima ``SELECT 1``.

    Raises:
        DatabaseConnectionError:
            Si no se puede establecer la conexión o ejecutar la consulta.
    """

    engine = get_engine()

    logger.info(
        "Comprobando conexión con la base de datos."
    )

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    except SQLAlchemyError as error:
        logger.exception(
            "No se pudo conectar con la base de datos."
        )

        raise DatabaseConnectionError(
            "No se pudo establecer conexión con PostgreSQL."
        ) from error

    logger.info(
        "Conexión con la base de datos verificada correctamente."
    )


def dispose_engine() -> None:
    """
    Cierra las conexiones mantenidas por el pool.

    Debe ejecutarse durante el apagado ordenado de la aplicación. Después de
    llamarlo, una futura llamada a ``get_engine`` creará un nuevo Engine.
    """

    global _engine
    global _session_factory

    with _initialization_lock:
        if _engine is None:
            return

        logger.info(
            "Cerrando el pool de conexiones de SQLAlchemy."
        )

        _engine.dispose()
        _engine = None
        _session_factory = None

        logger.info(
            "Pool de conexiones cerrado correctamente."
        )