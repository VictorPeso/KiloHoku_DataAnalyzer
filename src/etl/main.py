"""
Punto de entrada temporal de la aplicación.

Este archivo permite verificar que:

- El archivo .env se carga correctamente.
- La configuración general es válida.
- El directorio de logs se crea automáticamente.
- Los diferentes niveles de logging se almacenan correctamente.
- Las excepciones con traceback quedan registradas.
"""

from __future__ import annotations

# config debe importarse antes de inicializar el logger, ya que se encarga
# de cargar las variables del archivo .env.
from etl.config import settings
from etl.logger import configure_logging, get_logger


logger = get_logger(__name__)


def test_successful_operation() -> None:
    """
    Simula una operación ejecutada correctamente.
    """

    logger.info("Iniciando operación de prueba.")

    records_processed = 25

    logger.debug(
        "Procesando registros de prueba. records=%d",
        records_processed,
    )

    logger.info(
        "Operación de prueba completada. records=%d",
        records_processed,
    )


def test_warning() -> None:
    """
    Simula una situación no crítica que requiere atención.
    """

    logger.warning(
        "Se ha detectado una situación de prueba no crítica."
    )


def test_controlled_exception() -> None:
    """
    Simula una excepción controlada y registra su traceback.

    La excepción queda almacenada en application.log y errors.log, pero no
    finaliza la ejecución porque se captura dentro de esta función.
    """

    try:
        numerator = 10
        denominator = 0

        logger.debug(
            "Realizando división de prueba. numerator=%d denominator=%d",
            numerator,
            denominator,
        )

        _ = numerator / denominator

    except ZeroDivisionError:
        logger.exception(
            "Se ha producido una excepción controlada durante la prueba."
        )


def main() -> None:
    """
    Ejecuta las pruebas básicas del sistema de logging.
    """

    configure_logging()

    logger.info(
        "Aplicación iniciada. app_name=%s environment=%s",
        settings.app_name,
        settings.app_environment,
    )

    try:
        test_successful_operation()
        test_warning()
        test_controlled_exception()

        logger.info(
            "Todas las pruebas del logger han finalizado."
        )

    except Exception:
        logger.exception(
            "La aplicación ha finalizado debido a un error inesperado."
        )
        raise

    finally:
        logger.info("Aplicación finalizada.")


if __name__ == "__main__":
    main()