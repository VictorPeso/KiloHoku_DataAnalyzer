"""
Excepciones relacionadas con la transformación de datos.
"""

from __future__ import annotations


class TransformationError(ValueError):
    """
    Error producido al transformar un registro de entrada.

    Attributes:
        field_name:
            Nombre del campo que provocó el error.

        raw_value:
            Valor original que no pudo transformarse.

        row_number:
            Número de fila del archivo CSV.
    """

    def __init__(
        self,
        message: str,
        *,
        field_name: str | None = None,
        raw_value: object = None,
        row_number: int | None = None,
    ) -> None:
        self.field_name = field_name
        self.raw_value = raw_value
        self.row_number = row_number

        context_parts: list[str] = []

        if row_number is not None:
            context_parts.append(f"row={row_number}")

        if field_name is not None:
            context_parts.append(f"field={field_name}")

        if raw_value is not None:
            context_parts.append(f"value={raw_value!r}")

        if context_parts:
            complete_message = (
                f"{message} ({', '.join(context_parts)})"
            )
        else:
            complete_message = message

        super().__init__(complete_message)

class IrsaSourceTransformationError(TransformationError):
    """
    Error producido al transformar resultados posicionales de IRSA.

    Se utiliza cuando:

    - Faltan columnas necesarias.
    - Un oid no tiene un formato válido.
    - Una coordenada está fuera de rango.
    - IRSA devuelve un filtercode no soportado.
    - No puede construirse una fuente candidata.
    """