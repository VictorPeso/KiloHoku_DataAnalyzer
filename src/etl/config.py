"""
Configuración centralizada de la aplicación.

Este módulo se encarga de:

- Localizar el archivo .env.
- Cargar sus variables en el entorno.
- Validar la configuración general.
- Exponer una instancia global e inmutable de configuración.

No contiene ninguna configuración específica del logger, ya que logger.py
lee directamente las variables de entorno. Sin embargo, este módulo debe
cargarse antes de inicializar el sistema de logging.
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv


DEFAULT_APP_NAME: Final[str] = "data-processor"
DEFAULT_APP_ENV: Final[str] = "development"

VALID_ENVIRONMENTS: Final[set[str]] = {
    "development",
    "testing",
    "production",
}


def _find_project_root() -> Path:
    """
    Localiza la raíz del proyecto buscando el archivo .env.

    La búsqueda comienza en el directorio de este archivo y asciende por
    sus directorios padre hasta encontrar un archivo .env.

    Returns:
        Ruta absoluta al directorio raíz del proyecto.

    Raises:
        FileNotFoundError:
            Si no se encuentra ningún archivo .env.
    """

    current_directory = Path(__file__).resolve().parent

    for directory in (
        current_directory,
        *current_directory.parents,
    ):
        env_file = directory / ".env"

        if env_file.is_file():
            return directory

    raise FileNotFoundError(
        "No se ha encontrado el archivo .env. "
        "Debe estar situado en la raíz del proyecto."
    )


def _load_environment_file(project_root: Path) -> Path:
    """
    Carga las variables definidas en el archivo .env.

    Las variables ya existentes en el sistema no se sobrescriben. Esto
    permite que, en producción o Docker, las variables proporcionadas por
    el entorno tengan prioridad sobre el contenido del archivo .env.

    Args:
        project_root:
            Ruta raíz del proyecto.

    Returns:
        Ruta absoluta al archivo .env.
    """

    env_file = project_root / ".env"

    loaded = load_dotenv(
        dotenv_path=env_file,
        override=False,
        encoding="utf-8",
    )

    if not loaded:
        raise RuntimeError(
            f"No se pudo cargar el archivo de configuración: {env_file}"
        )

    return env_file


def _get_required_string(
    variable_name: str,
    default: str | None = None,
) -> str:
    """
    Obtiene una variable de entorno de tipo string.

    Args:
        variable_name:
            Nombre de la variable.

        default:
            Valor utilizado cuando la variable no está definida.

    Returns:
        Valor de la variable sin espacios exteriores.

    Raises:
        ValueError:
            Si la variable no existe, no tiene valor por defecto o está vacía.
    """

    value = os.getenv(variable_name, default)

    if value is None or not value.strip():
        raise ValueError(
            f"La variable de entorno {variable_name} es obligatoria."
        )

    return value.strip()


@dataclass(frozen=True, slots=True)
class Settings:
    """
    Configuración general de la aplicación.

    Attributes:
        app_name:
            Nombre identificativo de la aplicación.

        app_environment:
            Entorno actual: development, testing o production.

        project_root:
            Ruta absoluta a la raíz del proyecto.

        env_file:
            Ruta absoluta al archivo .env utilizado.
        
        irsa_search_radius_degrees:
            Radio de búsqueda en grados para consultas a IRSA.

        irsa_minimum_observations:
            Número mínimo de observaciones requerido para cada objeto en
            consultas a IRSA.
        
        irsa_bad_catalog_flags_mask:
            Máscara opcional para excluir observaciones con determinados
            catflags en consultas a IRSA.
        
        irsa_request_timeout_seconds:
            Tiempo máximo de espera en segundos para peticiones a IRSA.
        
        irsa_request_delay_seconds:
            Tiempo de espera en segundos entre peticiones a IRSA.
        
        irsa_max_retries:
            Número máximo de reintentos para peticiones a IRSA en caso de
            error.
    """

    app_name: str
    app_environment: str
    project_root: Path
    env_file: Path

    # IRSA / ZTF Light Curve API
    irsa_search_radius_degrees: float
    irsa_minimum_observations: int
    irsa_bad_catalog_flags_mask: int
    irsa_request_timeout_seconds: float
    irsa_request_delay_seconds: float
    irsa_max_retries: int

    @property
    def is_development(self) -> bool:
        """Indica si la aplicación se ejecuta en desarrollo."""

        return self.app_environment == "development"

    @property
    def is_testing(self) -> bool:
        """Indica si la aplicación se ejecuta en pruebas."""

        return self.app_environment == "testing"

    @property
    def is_production(self) -> bool:
        """Indica si la aplicación se ejecuta en producción."""

        return self.app_environment == "production"
    
    @property
    def irsa_search_radius_arcseconds(self) -> float:
        """
        Devuelve el radio de búsqueda de IRSA en segundos de arco.
        """

        return self.irsa_search_radius_degrees * 3600.0
    
    @property
    def irsa_retry_attempts(self) -> int:
        """
        Devuelve el número total máximo de peticiones.

        Incluye la petición inicial y los reintentos posteriores.
        """

        return self.irsa_max_retries


def _create_settings() -> Settings:
    """
    Carga y valida la configuración de la aplicación.

    Returns:
        Instancia inmutable de Settings.

    Raises:
        ValueError:
            Si alguna variable contiene un valor inválido.
    """

    project_root = _find_project_root()
    env_file = _load_environment_file(project_root)

    app_name = _get_required_string(
        "APP_NAME",
        DEFAULT_APP_NAME,
    )

    app_environment = _get_required_string(
        "APP_ENV",
        DEFAULT_APP_ENV,
    ).lower()

    irsa_search_radius_degrees=_get_positive_float(
        "IRSA_SEARCH_RADIUS_DEGREES",
        default=0.00042,
    )
    irsa_minimum_observations=_get_positive_integer(
        "IRSA_MINIMUM_OBSERVATIONS",
        default=15,
    )
    irsa_bad_catalog_flags_mask=_get_non_negative_integer(
        "IRSA_BAD_CATALOG_FLAGS_MASK",
        default=65535,
    )
    irsa_request_timeout_seconds=_get_positive_float(
        "IRSA_REQUEST_TIMEOUT_SECONDS",
        default=60.0,
    )
    irsa_request_delay_seconds=_get_non_negative_float(
        "IRSA_REQUEST_DELAY_SECONDS",
        default=1.0,
    )
    irsa_max_retries=_get_positive_integer(
        "IRSA_MAX_RETRIES",
        default=5,
    )

    if app_environment not in VALID_ENVIRONMENTS:
        valid_values = ", ".join(sorted(VALID_ENVIRONMENTS))

        raise ValueError(
            f"APP_ENV contiene un valor inválido: "
            f"{app_environment!r}. Valores válidos: {valid_values}."
        )

    return Settings(
        app_name=app_name,
        app_environment=app_environment,
        project_root=project_root,
        env_file=env_file,
        irsa_search_radius_degrees=irsa_search_radius_degrees,
        irsa_minimum_observations=irsa_minimum_observations,
        irsa_bad_catalog_flags_mask=irsa_bad_catalog_flags_mask,
        irsa_request_timeout_seconds=irsa_request_timeout_seconds,
        irsa_request_delay_seconds=irsa_request_delay_seconds,
        irsa_max_retries=irsa_max_retries,
    )

def _get_positive_float(
    variable_name: str,
    *,
    default: float,
) -> float:
    """
    Lee una variable de entorno como número real positivo.

    Args:
        variable_name:
            Nombre de la variable de entorno.

        default:
            Valor utilizado cuando la variable no está definida.

    Returns:
        Número real finito y mayor que cero.

    Raises:
        ValueError:
            Si el valor no es numérico, no es finito o no es positivo.
    """

    raw_value = os.getenv(
        variable_name,
        str(default),
    ).strip()

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(
            f"{variable_name} debe contener un número real. "
            f"Valor recibido: {raw_value!r}."
        ) from error

    if not math.isfinite(value):
        raise ValueError(
            f"{variable_name} debe contener un número finito. "
            f"Valor recibido: {raw_value!r}."
        )

    if value <= 0:
        raise ValueError(
            f"{variable_name} debe ser mayor que cero. "
            f"Valor recibido: {value}."
        )

    return value

def _get_non_negative_float(
    variable_name: str,
    *,
    default: float,
) -> float:
    """
    Lee una variable de entorno como número real no negativo.

    Se utiliza para valores como el tiempo mínimo entre peticiones, donde
    cero permite desactivar la espera.

    Args:
        variable_name:
            Nombre de la variable de entorno.

        default:
            Valor utilizado cuando la variable no está definida.

    Returns:
        Número real finito igual o superior a cero.

    Raises:
        ValueError:
            Si el valor no es numérico, no es finito o es negativo.
    """

    raw_value = os.getenv(
        variable_name,
        str(default),
    ).strip()

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(
            f"{variable_name} debe contener un número real. "
            f"Valor recibido: {raw_value!r}."
        ) from error

    if not math.isfinite(value):
        raise ValueError(
            f"{variable_name} debe contener un número finito. "
            f"Valor recibido: {raw_value!r}."
        )

    if value < 0:
        raise ValueError(
            f"{variable_name} no puede ser negativo. "
            f"Valor recibido: {value}."
        )

    return value

def _get_positive_integer(
    variable_name: str,
    *,
    default: int,
) -> int:
    """
    Lee una variable de entorno como número entero positivo.

    Args:
        variable_name:
            Nombre de la variable de entorno.

        default:
            Valor utilizado cuando la variable no está definida.

    Returns:
        Número entero mayor que cero.

    Raises:
        ValueError:
            Si el valor no es un entero o no es positivo.
    """

    raw_value = os.getenv(
        variable_name,
        str(default),
    ).strip()

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(
            f"{variable_name} debe contener un número entero. "
            f"Valor recibido: {raw_value!r}."
        ) from error

    if value <= 0:
        raise ValueError(
            f"{variable_name} debe ser mayor que cero. "
            f"Valor recibido: {value}."
        )

    return value

def _get_non_negative_integer(
    variable_name: str,
    *,
    default: int,
) -> int:
    """
    Lee una variable de entorno como número entero no negativo.

    Args:
        variable_name:
            Nombre de la variable de entorno.

        default:
            Valor utilizado cuando la variable no está definida.

    Returns:
        Número entero igual o superior a cero.

    Raises:
        ValueError:
            Si el valor no es un entero o es negativo.
    """

    raw_value = os.getenv(
        variable_name,
        str(default),
    ).strip()

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(
            f"{variable_name} debe contener un número entero. "
            f"Valor recibido: {raw_value!r}."
        ) from error

    if value < 0:
        raise ValueError(
            f"{variable_name} no puede ser negativo. "
            f"Valor recibido: {value}."
        )

    return value

settings = _create_settings()