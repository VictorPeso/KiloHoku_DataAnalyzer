"""
Excepciones de la capa de extracción.

Todas las excepciones propias de los extractores heredan de
``ExtractionError``.

Esto permite capturar:

- Todos los errores de extracción de forma general.
- Errores concretos cuando se necesita un tratamiento específico.
"""


class ExtractionError(RuntimeError):
    """
    Error base producido durante la extracción de datos.
    """


class SourceFileNotFoundError(ExtractionError):
    """
    Error producido cuando un archivo de origen no existe.
    """


class InvalidCsvStructureError(ExtractionError):
    """
    Error producido cuando un CSV no tiene la estructura esperada.
    """


class InvalidVOTableError(ExtractionError):
    """
    Error producido cuando un VOTable no tiene una estructura válida.
    """


class VOTableRowError(ExtractionError):
    """
    Error producido al convertir una fila de un VOTable.
    """


class ApiExtractionError(ExtractionError):
    """
    Error base producido al consultar una API externa.
    """


class ApiConnectionError(ApiExtractionError):
    """
    Error de red, conexión o tiempo de espera al consultar una API.
    """


class ApiResponseError(ApiExtractionError):
    """
    Error producido cuando una API devuelve una respuesta inválida.
    """


class IrsaClientError(ApiExtractionError):
    """
    Error base específico del cliente NASA/IPAC IRSA.
    """


class IrsaConnectionError(IrsaClientError):
    """
    Error de conexión o timeout al consultar IRSA.
    """


class IrsaResponseError(IrsaClientError):
    """
    Error producido por una respuesta inválida de IRSA.
    """