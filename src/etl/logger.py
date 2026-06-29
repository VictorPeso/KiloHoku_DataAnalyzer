"""
Configuración centralizada del sistema de logging.

Este módulo configura el logging de la aplicación para que todos los mensajes
se almacenen en archivos rotativos, sin escribir información en la consola.

Estructura generada por defecto:

logs/
├── application/
│   ├── application.log
│   ├── application.log.2026-06-28
│   └── ...
└── errors/
    ├── errors.log
    ├── errors.log.2026-06-28
    └── ...

Variables de entorno disponibles:

LOG_DIR
    Directorio raíz de los logs.
    Valor por defecto: logs

LOG_LEVEL
    Nivel mínimo registrado en application.log.
    Valor por defecto: INFO

LOG_RETENTION_DAYS
    Número de archivos históricos conservados.
    Valor por defecto: 30

LOG_UTC
    Indica si las fechas deben registrarse en UTC.
    Valores válidos: true, false, 1, 0, yes, no
    Valor por defecto: true
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Final
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DEFAULT_LOG_DIRECTORY: Final[str] = "logs"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_RETENTION_DAYS: Final[int] = 30

APPLICATION_LOGGER_NAME: Final[str] = "data_processor"

_APPLICATION_LOG_DIRECTORY: Final[str] = "application"
_ERROR_LOG_DIRECTORY: Final[str] = "errors"

_APPLICATION_LOG_FILENAME: Final[str] = "application.log"
_ERROR_LOG_FILENAME: Final[str] = "errors.log"

_LOG_FORMAT: Final[str] = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(message)s | "
    "%(name)s | "
    "%(module)s.%(funcName)s:%(lineno)d | "
    "run=%(run_id)s | "
    "process=%(process)d | "
    "thread=%(threadName)s"
)

_configured = False
_run_id = uuid.uuid4().hex


class RunIdFilter(logging.Filter):
    """
    Añade el identificador de ejecución a cada registro de logging.

    El identificador permite relacionar todos los mensajes generados durante
    una misma ejecución del proceso.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self._run_id
        return True


class ApplicationLogFilter(logging.Filter):
    """
    Filtra los mensajes que deben almacenarse en application.log.

    Se registran todos los mensajes cuyo nivel sea igual o superior al nivel
    configurado para la aplicación.
    """

    def __init__(self, minimum_level: int) -> None:
        super().__init__()
        self._minimum_level = minimum_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self._minimum_level


class ErrorLogFilter(logging.Filter):
    """
    Permite únicamente mensajes ERROR o CRITICAL.

    De esta forma, errors.log contiene solamente errores que requieren
    atención, mientras que application.log conserva la secuencia completa
    de ejecución.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


class ProductionFormatter(logging.Formatter):
    """
    Formateador que genera fechas ISO 8601 con una zona horaria explícita.
    """

    def __init__(
        self,
        fmt: str,
        *,
        use_utc: bool,
        timezone_name: str,
    ) -> None:
        super().__init__(fmt=fmt)

        if use_utc:
            self._timezone = timezone.utc
        else:
            self._timezone = ZoneInfo(timezone_name)

    def formatTime(
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        """
        Devuelve la fecha del registro en formato ISO 8601.
        """

        log_datetime = datetime.fromtimestamp(
            record.created,
            tz=self._timezone,
        )

        return log_datetime.isoformat(
            timespec="seconds",
        )


def _get_boolean_environment_variable(
    variable_name: str,
    default: bool,
) -> bool:
    """
    Obtiene una variable de entorno booleana.

    Args:
        variable_name:
            Nombre de la variable de entorno.

        default:
            Valor utilizado cuando la variable no está definida.

    Returns:
        El valor booleano interpretado.

    Raises:
        ValueError:
            Si el valor definido no representa un booleano válido.
    """

    value = os.getenv(variable_name)

    if value is None:
        return default

    normalized_value = value.strip().lower()

    true_values = {"1", "true", "yes", "y", "on"}
    false_values = {"0", "false", "no", "n", "off"}

    if normalized_value in true_values:
        return True

    if normalized_value in false_values:
        return False

    raise ValueError(
        f"La variable de entorno {variable_name} debe contener un valor "
        f"booleano válido. Valor recibido: {value!r}"
    )


def _get_log_level() -> int:
    """
    Obtiene y valida el nivel de logging configurado.

    Returns:
        Nivel numérico compatible con el módulo logging.

    Raises:
        ValueError:
            Si LOG_LEVEL contiene un nivel desconocido.
    """

    configured_level = os.getenv(
        "LOG_LEVEL",
        DEFAULT_LOG_LEVEL,
    ).strip().upper()

    numeric_level = logging.getLevelNamesMapping().get(configured_level)

    if numeric_level is None:
        valid_levels = (
            "DEBUG, INFO, WARNING, ERROR y CRITICAL"
        )

        raise ValueError(
            f"Nivel de logging no válido: {configured_level!r}. "
            f"Valores habituales: {valid_levels}."
        )

    return numeric_level


def _get_retention_days() -> int:
    """
    Obtiene el número de días durante los que se conservan los logs.

    Returns:
        Número de archivos históricos conservados.

    Raises:
        ValueError:
            Si LOG_RETENTION_DAYS no es un entero positivo.
    """

    configured_value = os.getenv(
        "LOG_RETENTION_DAYS",
        str(DEFAULT_RETENTION_DAYS),
    )

    try:
        retention_days = int(configured_value)
    except ValueError as error:
        raise ValueError(
            "LOG_RETENTION_DAYS debe ser un número entero."
        ) from error

    if retention_days < 1:
        raise ValueError(
            "LOG_RETENTION_DAYS debe ser igual o superior a 1."
        )

    return retention_days


def _create_log_directories(
    root_directory: Path,
) -> tuple[Path, Path]:
    """
    Crea los directorios donde se almacenarán los logs.

    Args:
        root_directory:
            Directorio raíz de logs.

    Returns:
        Tupla con el directorio de aplicación y el directorio de errores.
    """

    application_directory = (
        root_directory / _APPLICATION_LOG_DIRECTORY
    )
    error_directory = root_directory / _ERROR_LOG_DIRECTORY

    application_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    error_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return application_directory, error_directory


def _create_rotating_file_handler(
    file_path: Path,
    *,
    retention_days: int,
    formatter: logging.Formatter,
    log_filter: logging.Filter,
) -> TimedRotatingFileHandler:
    """
    Crea un handler de archivo con rotación diaria.

    La rotación se realiza cada medianoche. Los archivos anteriores reciben
    un sufijo con su fecha, por ejemplo:

        application.log.2026-06-28

    Args:
        file_path:
            Ruta del archivo de log actual.

        retention_days:
            Número de archivos históricos que se conservarán.

        formatter:
            Formateador aplicado a cada registro.

        log_filter:
            Filtro aplicado al handler.

    Returns:
        Handler configurado.
    """

    handler = TimedRotatingFileHandler(
        filename=file_path,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        delay=True,
    )

    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(formatter)
    handler.addFilter(log_filter)
    handler.addFilter(RunIdFilter(_run_id))

    return handler


def configure_logging() -> None:
    """
    Configura el sistema de logging de toda la aplicación.

    Esta función es idempotente: puede llamarse varias veces sin duplicar
    handlers ni repetir mensajes.

    Debe ejecutarse una vez al arrancar el programa, antes de comenzar
    cualquier pipeline o tarea.

    Raises:
        OSError:
            Si no pueden crearse los directorios o archivos de logs.

        ValueError:
            Si alguna variable de entorno contiene un valor inválido.
    """

    global _configured

    if _configured:
        return

    log_root_directory = Path(
        os.getenv(
            "LOG_DIR",
            DEFAULT_LOG_DIRECTORY,
        )
    ).expanduser().resolve()

    log_level = _get_log_level()
    retention_days = _get_retention_days()
    use_utc = _get_boolean_environment_variable(
        "LOG_UTC",
        default=True,
    )

    timezone_name = os.getenv(
        "LOG_TIMEZONE",
        "Europe/Madrid",
    ).strip()

    application_directory, error_directory = (
        _create_log_directories(log_root_directory)
    )

    formatter = ProductionFormatter(
        fmt=_LOG_FORMAT,
        use_utc=use_utc,
        timezone_name=timezone_name,
    )

    application_handler = _create_rotating_file_handler(
        application_directory / _APPLICATION_LOG_FILENAME,
        retention_days=retention_days,
        formatter=formatter,
        log_filter=ApplicationLogFilter(log_level),
    )

    error_handler = _create_rotating_file_handler(
        error_directory / _ERROR_LOG_FILENAME,
        retention_days=retention_days,
        formatter=formatter,
        log_filter=ErrorLogFilter(),
    )

    root_logger = logging.getLogger()

    # El nivel raíz debe ser DEBUG para permitir que sean los filtros de cada
    # handler quienes decidan qué mensajes deben almacenarse.
    root_logger.setLevel(logging.DEBUG)

    # Eliminamos cualquier handler previo para garantizar que no se escriba
    # en consola ni se dupliquen mensajes.
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)
        existing_handler.close()

    root_logger.addHandler(application_handler)
    root_logger.addHandler(error_handler)

    logging.captureWarnings(True)

    _install_uncaught_exception_handlers()

    _configured = True

    logger = logging.getLogger(APPLICATION_LOGGER_NAME)

    logger.info(
        "Sistema de logging configurado. "
        "log_directory=%s log_level=%s retention_days=%d utc=%s",
        log_root_directory,
        logging.getLevelName(log_level),
        retention_days,
        use_utc,
    )


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Obtiene un logger configurado para un módulo.

    Si el sistema de logging todavía no está configurado, se configura
    automáticamente.

    Args:
        name:
            Nombre del logger. Normalmente debe pasarse ``__name__``.

    Returns:
        Logger listo para utilizar.
    """

    configure_logging()

    if name is None:
        return logging.getLogger(APPLICATION_LOGGER_NAME)

    return logging.getLogger(name)


def _handle_uncaught_exception(
    exception_type: type[BaseException],
    exception_value: BaseException,
    exception_traceback: TracebackType | None,
) -> None:
    """
    Registra excepciones no capturadas del hilo principal.
    """

    if issubclass(exception_type, KeyboardInterrupt):
        sys.__excepthook__(
            exception_type,
            exception_value,
            exception_traceback,
        )
        return

    logger = logging.getLogger(APPLICATION_LOGGER_NAME)

    logger.critical(
        "Excepción no controlada. El proceso finalizará.",
        exc_info=(
            exception_type,
            exception_value,
            exception_traceback,
        ),
    )


def _handle_thread_exception(
    exception_arguments: threading.ExceptHookArgs,
) -> None:
    """
    Registra excepciones no capturadas producidas en otros hilos.
    """

    if exception_arguments.exc_type is KeyboardInterrupt:
        return

    logger = logging.getLogger(APPLICATION_LOGGER_NAME)

    logger.critical(
        "Excepción no controlada en el hilo %s.",
        exception_arguments.thread.name
        if exception_arguments.thread
        else "desconocido",
        exc_info=(
            exception_arguments.exc_type,
            exception_arguments.exc_value,
            exception_arguments.exc_traceback,
        ),
    )


def _install_uncaught_exception_handlers() -> None:
    """
    Instala los manejadores globales de excepciones no controladas.
    """

    sys.excepthook = _handle_uncaught_exception
    threading.excepthook = _handle_thread_exception