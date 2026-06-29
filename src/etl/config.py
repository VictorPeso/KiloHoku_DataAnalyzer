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
    """

    app_name: str
    app_environment: str
    project_root: Path
    env_file: Path

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
    )


settings = _create_settings()