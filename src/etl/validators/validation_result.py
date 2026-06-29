"""
Modelos utilizados para representar resultados de validación.

Este módulo permite distinguir entre:

- Errores bloqueantes, que impiden continuar con el procesamiento.
- Advertencias, que indican problemas de calidad pero no invalidan el dato.
- Mensajes informativos, que aportan contexto adicional.

Los validadores devolverán un ValidationResult en lugar de lanzar
excepciones por cada problema encontrado. De esta forma es posible recopilar
varios errores y advertencias en una sola ejecución.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ValidationSeverity(StrEnum):
    """
    Nivel de severidad de una incidencia de validación.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationIssue:
    """
    Representa una incidencia detectada durante una validación.

    Attributes:
        code:
            Código estable que identifica el tipo de incidencia.

            Ejemplos:

                MISSING_DATA_FILE
                INVALID_GAIA_MAGNITUDE
                DUPLICATE_ALERT_ID

        message:
            Descripción legible del problema.

        severity:
            Nivel de severidad de la incidencia.

        field_name:
            Nombre del atributo relacionado con el problema, si aplica.

        value:
            Valor que provocó la incidencia, si resulta útil registrarlo.
    """

    code: str
    message: str
    severity: ValidationSeverity
    field_name: str | None = None
    value: Any | None = None

    def __post_init__(self) -> None:
        """
        Valida la estructura básica de la incidencia.
        """

        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError(
                "ValidationIssue.code debe ser un string no vacío."
            )

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError(
                "ValidationIssue.message debe ser un string no vacío."
            )

        if not isinstance(self.severity, ValidationSeverity):
            raise TypeError(
                "ValidationIssue.severity debe ser ValidationSeverity."
            )

        if self.field_name is not None:
            if (
                not isinstance(self.field_name, str)
                or not self.field_name.strip()
            ):
                raise ValueError(
                    "ValidationIssue.field_name debe ser un string "
                    "no vacío o None."
                )


@dataclass(slots=True)
class ValidationResult:
    """
    Contiene el resultado completo de una validación.

    Un resultado se considera válido cuando no contiene incidencias con
    severidad ERROR.

    Las advertencias y mensajes informativos no invalidan el objeto.

    Attributes:
        issues:
            Incidencias detectadas durante la validación.
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Indica si la validación ha sido superada.

        Returns:
            True cuando no existe ninguna incidencia de tipo ERROR.
        """

        return not self.has_errors

    @property
    def has_errors(self) -> bool:
        """
        Indica si existen errores bloqueantes.
        """

        return any(
            issue.severity is ValidationSeverity.ERROR
            for issue in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        """
        Indica si existen advertencias.
        """

        return any(
            issue.severity is ValidationSeverity.WARNING
            for issue in self.issues
        )

    @property
    def has_info(self) -> bool:
        """
        Indica si existen mensajes informativos.
        """

        return any(
            issue.severity is ValidationSeverity.INFO
            for issue in self.issues
        )

    @property
    def errors(self) -> list[ValidationIssue]:
        """
        Devuelve únicamente las incidencias de tipo ERROR.
        """

        return self.get_issues_by_severity(
            ValidationSeverity.ERROR
        )

    @property
    def warnings(self) -> list[ValidationIssue]:
        """
        Devuelve únicamente las incidencias de tipo WARNING.
        """

        return self.get_issues_by_severity(
            ValidationSeverity.WARNING
        )

    @property
    def info(self) -> list[ValidationIssue]:
        """
        Devuelve únicamente las incidencias de tipo INFO.
        """

        return self.get_issues_by_severity(
            ValidationSeverity.INFO
        )

    @property
    def error_count(self) -> int:
        """
        Devuelve el número de errores bloqueantes.
        """

        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """
        Devuelve el número de advertencias.
        """

        return len(self.warnings)

    @property
    def info_count(self) -> int:
        """
        Devuelve el número de mensajes informativos.
        """

        return len(self.info)

    @property
    def issue_count(self) -> int:
        """
        Devuelve el número total de incidencias.
        """

        return len(self.issues)

    def add_issue(
        self,
        issue: ValidationIssue,
    ) -> None:
        """
        Añade una incidencia al resultado.

        Args:
            issue:
                Incidencia que debe almacenarse.
        """

        if not isinstance(issue, ValidationIssue):
            raise TypeError(
                "issue debe ser una instancia de ValidationIssue."
            )

        self.issues.append(issue)

    def add_error(
        self,
        *,
        code: str,
        message: str,
        field_name: str | None = None,
        value: Any | None = None,
    ) -> None:
        """
        Añade un error bloqueante.
        """

        self.add_issue(
            ValidationIssue(
                code=code,
                message=message,
                severity=ValidationSeverity.ERROR,
                field_name=field_name,
                value=value,
            )
        )

    def add_warning(
        self,
        *,
        code: str,
        message: str,
        field_name: str | None = None,
        value: Any | None = None,
    ) -> None:
        """
        Añade una advertencia no bloqueante.
        """

        self.add_issue(
            ValidationIssue(
                code=code,
                message=message,
                severity=ValidationSeverity.WARNING,
                field_name=field_name,
                value=value,
            )
        )

    def add_info(
        self,
        *,
        code: str,
        message: str,
        field_name: str | None = None,
        value: Any | None = None,
    ) -> None:
        """
        Añade un mensaje informativo.
        """

        self.add_issue(
            ValidationIssue(
                code=code,
                message=message,
                severity=ValidationSeverity.INFO,
                field_name=field_name,
                value=value,
            )
        )

    def extend(
        self,
        other: ValidationResult,
    ) -> None:
        """
        Incorpora las incidencias de otro resultado de validación.

        Esto permite dividir un validator en varias comprobaciones y combinar
        después todos sus resultados.

        Args:
            other:
                Resultado cuyas incidencias deben añadirse.
        """

        if not isinstance(other, ValidationResult):
            raise TypeError(
                "other debe ser una instancia de ValidationResult."
            )

        self.issues.extend(other.issues)

    def get_issues_by_severity(
        self,
        severity: ValidationSeverity,
    ) -> list[ValidationIssue]:
        """
        Filtra incidencias por nivel de severidad.

        Args:
            severity:
                Severidad que debe seleccionarse.

        Returns:
            Nueva lista con las incidencias coincidentes.
        """

        if not isinstance(severity, ValidationSeverity):
            raise TypeError(
                "severity debe ser ValidationSeverity."
            )

        return [
            issue
            for issue in self.issues
            if issue.severity is severity
        ]

    def get_issues_for_field(
        self,
        field_name: str,
    ) -> list[ValidationIssue]:
        """
        Devuelve las incidencias asociadas a un campo concreto.

        Args:
            field_name:
                Nombre del campo que se desea consultar.
        """

        if not isinstance(field_name, str) or not field_name.strip():
            raise ValueError(
                "field_name debe ser un string no vacío."
            )

        return [
            issue
            for issue in self.issues
            if issue.field_name == field_name
        ]

    def merge(
        self,
        *results: ValidationResult,
    ) -> ValidationResult:
        """
        Crea un nuevo resultado combinando varios resultados.

        El objeto actual no se modifica.

        Args:
            results:
                Resultados adicionales que deben combinarse.

        Returns:
            Nuevo ValidationResult con todas las incidencias.
        """

        merged_result = ValidationResult(
            issues=list(self.issues)
        )

        for result in results:
            merged_result.extend(result)

        return merged_result

    @classmethod
    def valid(cls) -> ValidationResult:
        """
        Crea un resultado válido sin incidencias.
        """

        return cls()

    @classmethod
    def from_error(
        cls,
        *,
        code: str,
        message: str,
        field_name: str | None = None,
        value: Any | None = None,
    ) -> ValidationResult:
        """
        Crea un resultado que contiene un único error.
        """

        result = cls()

        result.add_error(
            code=code,
            message=message,
            field_name=field_name,
            value=value,
        )

        return result