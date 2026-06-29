"""
Validador de calidad para candidatos estelares.

Este módulo aplica reglas de validación adicionales sobre una entidad
StarCandidate ya transformada.

La entidad StarCandidate garantiza que los tipos y las invariantes básicas
sean correctos. Este validator se centra en la calidad, coherencia y
completitud de los datos.

Las reglas pueden producir:

- ERROR:
    El candidato no debería continuar hacia la siguiente etapa del ETL.

- WARNING:
    El candidato puede continuar, pero presenta datos incompletos o
    potencialmente anómalos.

- INFO:
    Información útil sobre el candidato que no representa un problema.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from etl.domain.entities import StarCandidate
from etl.logger import get_logger
from etl.validators.validation_result import ValidationResult


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class StarCandidateValidationConfig:
    """
    Configuración de las reglas de validación.

    Attributes:
        maximum_angular_distance:
            Distancia angular máxima considerada razonable para asociar
            un candidato con un objeto de SIMBAD.

        maximum_parallax_relative_error:
            Máximo error relativo aceptable para la paralaje.

            Se calcula como:

                parallax_error / abs(parallax)

            Una razón superior a este valor genera una advertencia.

        minimum_gaia_magnitude:
            Magnitud mínima razonable para las bandas Gaia.

        maximum_gaia_magnitude:
            Magnitud máxima razonable para las bandas Gaia.

        maximum_color_index:
            Valor absoluto máximo considerado razonable para la diferencia
            entre magnitudes BP y RP.

        require_generated_resources:
            Si es True, la ausencia de archivo de datos o gráfica se
            considera un error.

            Si es False, se considera únicamente una advertencia.

        require_simbad_match:
            Si es True, la ausencia de asociación con SIMBAD se considera
            un error.

            Si es False, se registra como información.
    """

    maximum_angular_distance: float = 5.0
    maximum_parallax_relative_error: float = 1.0

    minimum_gaia_magnitude: float = -5.0
    maximum_gaia_magnitude: float = 30.0

    maximum_color_index: float = 10.0

    require_generated_resources: bool = False
    require_simbad_match: bool = False

    def __post_init__(self) -> None:
        """
        Valida la propia configuración.
        """

        if self.maximum_angular_distance < 0:
            raise ValueError(
                "maximum_angular_distance no puede ser negativa."
            )

        if self.maximum_parallax_relative_error < 0:
            raise ValueError(
                "maximum_parallax_relative_error no puede ser negativa."
            )

        if self.minimum_gaia_magnitude >= self.maximum_gaia_magnitude:
            raise ValueError(
                "minimum_gaia_magnitude debe ser menor que "
                "maximum_gaia_magnitude."
            )

        if self.maximum_color_index < 0:
            raise ValueError(
                "maximum_color_index no puede ser negativo."
            )


class StarCandidateValidator:
    """
    Valida la calidad y coherencia de una entidad StarCandidate.

    El validator no modifica la entidad ni lanza excepciones por cada
    incidencia detectada. Devuelve un ValidationResult con todos los
    problemas encontrados.
    """

    _GAIA_MAGNITUDE_FIELDS: Final[tuple[str, ...]] = (
        "gaia_g_magnitude",
        "gaia_bp_magnitude",
        "gaia_rp_magnitude",
    )

    def __init__(
        self,
        config: StarCandidateValidationConfig | None = None,
    ) -> None:
        """
        Inicializa el validator.

        Args:
            config:
                Configuración de las reglas. Si no se proporciona, se
                utilizan los valores por defecto.
        """

        self._config = config or StarCandidateValidationConfig()

    @property
    def config(self) -> StarCandidateValidationConfig:
        """
        Devuelve la configuración del validator.
        """

        return self._config

    def validate(
        self,
        candidate: StarCandidate,
    ) -> ValidationResult:
        """
        Valida un único candidato estelar.

        Args:
            candidate:
                Entidad que debe validarse.

        Returns:
            Resultado completo de la validación.

        Raises:
            TypeError:
                Si el objeto recibido no es StarCandidate.
        """

        if not isinstance(candidate, StarCandidate):
            raise TypeError(
                "candidate debe ser una instancia de StarCandidate."
            )

        result = ValidationResult()

        self._validate_simbad_match(candidate, result)
        self._validate_generated_resources(candidate, result)
        self._validate_gaia_magnitudes(candidate, result)
        self._validate_color_index(candidate, result)
        self._validate_parallax(candidate, result)
        self._validate_spectrum_and_emission(candidate, result)
        self._add_classification_information(candidate, result)

        logger.debug(
            "Candidato validado. alert_id=%s valid=%s errors=%d "
            "warnings=%d info=%d",
            candidate.alert_id,
            result.is_valid,
            result.error_count,
            result.warning_count,
            result.info_count,
        )

        return result

    def validate_many(
        self,
        candidates: Iterable[StarCandidate],
    ) -> list[ValidationResult]:
        """
        Valida una colección de candidatos.

        Args:
            candidates:
                Colección de entidades StarCandidate.

        Returns:
            Lista de resultados en el mismo orden que los candidatos.
        """

        results: list[ValidationResult] = []

        for candidate in candidates:
            results.append(self.validate(candidate))

        return results

    def _validate_simbad_match(
        self,
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Comprueba la coherencia de la asociación con SIMBAD.
        """

        has_target = candidate.closest_simbad_target is not None
        has_distance = candidate.angular_distance is not None

        if has_target and not has_distance:
            result.add_error(
                code="SIMBAD_TARGET_WITHOUT_DISTANCE",
                message=(
                    "Existe un objeto asociado de SIMBAD, pero no se ha "
                    "proporcionado su distancia angular."
                ),
                field_name="angular_distance",
            )
            return

        if has_distance and not has_target:
            result.add_error(
                code="SIMBAD_DISTANCE_WITHOUT_TARGET",
                message=(
                    "Existe una distancia angular, pero no se ha "
                    "proporcionado el objeto asociado de SIMBAD."
                ),
                field_name="closest_simbad_target",
            )
            return

        if not has_target and not has_distance:
            if self._config.require_simbad_match:
                result.add_error(
                    code="MISSING_SIMBAD_MATCH",
                    message=(
                        "El candidato no tiene ninguna asociación con "
                        "SIMBAD."
                    ),
                    field_name="closest_simbad_target",
                )
            else:
                result.add_info(
                    code="NO_SIMBAD_MATCH",
                    message=(
                        "El candidato no tiene ninguna asociación con "
                        "SIMBAD."
                    ),
                    field_name="closest_simbad_target",
                )

            return

        angular_distance = candidate.angular_distance

        if (
            angular_distance is not None
            and angular_distance
            > self._config.maximum_angular_distance
        ):
            result.add_warning(
                code="LARGE_SIMBAD_ANGULAR_DISTANCE",
                message=(
                    "La asociación con SIMBAD presenta una distancia "
                    "angular superior al límite configurado."
                ),
                field_name="angular_distance",
                value=angular_distance,
            )

    def _validate_generated_resources(
        self,
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Comprueba la disponibilidad del archivo de datos y de la gráfica.
        """

        has_data_file = candidate.data_file_url is not None
        has_plot = candidate.plot_url is not None

        if has_data_file and has_plot:
            return

        if has_data_file and not has_plot:
            result.add_warning(
                code="DATA_FILE_WITHOUT_PLOT",
                message=(
                    "El candidato tiene un archivo de datos, pero no tiene "
                    "una gráfica asociada."
                ),
                field_name="plot_url",
            )
            return

        if has_plot and not has_data_file:
            result.add_warning(
                code="PLOT_WITHOUT_DATA_FILE",
                message=(
                    "El candidato tiene una gráfica, pero no tiene un "
                    "archivo de datos asociado."
                ),
                field_name="data_file_url",
            )
            return

        if self._config.require_generated_resources:
            result.add_error(
                code="MISSING_GENERATED_RESOURCES",
                message=(
                    "El candidato no tiene archivo de datos ni gráfica "
                    "asociada."
                ),
                field_name="data_file_url",
            )
        else:
            result.add_warning(
                code="MISSING_GENERATED_RESOURCES",
                message=(
                    "El candidato no tiene archivo de datos ni gráfica "
                    "asociada."
                ),
                field_name="data_file_url",
            )

    def _validate_gaia_magnitudes(
        self,
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Comprueba que las magnitudes Gaia estén en un rango razonable.
        """

        magnitudes = {
            "gaia_g_magnitude": candidate.gaia_g_magnitude,
            "gaia_bp_magnitude": candidate.gaia_bp_magnitude,
            "gaia_rp_magnitude": candidate.gaia_rp_magnitude,
        }

        for field_name, magnitude in magnitudes.items():
            if (
                magnitude < self._config.minimum_gaia_magnitude
                or magnitude > self._config.maximum_gaia_magnitude
            ):
                result.add_warning(
                    code="GAIA_MAGNITUDE_OUT_OF_EXPECTED_RANGE",
                    message=(
                        "La magnitud Gaia se encuentra fuera del rango "
                        "esperado configurado."
                    ),
                    field_name=field_name,
                    value=magnitude,
                )

    def _validate_color_index(
        self,
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Comprueba el índice de color BP-RP.
        """

        color_index = (
            candidate.gaia_bp_magnitude
            - candidate.gaia_rp_magnitude
        )

        if abs(color_index) > self._config.maximum_color_index:
            result.add_warning(
                code="EXTREME_BP_RP_COLOR_INDEX",
                message=(
                    "El índice de color BP-RP tiene un valor absoluto "
                    "superior al límite configurado."
                ),
                field_name="gaia_bp_magnitude",
                value=color_index,
            )

    def _validate_parallax(
        self,
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Comprueba la calidad relativa de la paralaje.
        """

        if candidate.parallax == 0:
            if candidate.parallax_error > 0:
                result.add_warning(
                    code="ZERO_PARALLAX_WITH_ERROR",
                    message=(
                        "La paralaje es cero y tiene una incertidumbre "
                        "asociada."
                    ),
                    field_name="parallax",
                    value=candidate.parallax,
                )

            return

        relative_error = (
            candidate.parallax_error
            / abs(candidate.parallax)
        )

        if (
            relative_error
            > self._config.maximum_parallax_relative_error
        ):
            result.add_warning(
                code="HIGH_PARALLAX_RELATIVE_ERROR",
                message=(
                    "El error relativo de la paralaje supera el límite "
                    "configurado."
                ),
                field_name="parallax_error",
                value=relative_error,
            )

        if candidate.parallax < 0:
            result.add_info(
                code="NEGATIVE_PARALLAX",
                message=(
                    "La paralaje medida es negativa. Puede tratarse de una "
                    "medición compatible con ruido o alta incertidumbre."
                ),
                field_name="parallax",
                value=candidate.parallax,
            )

    @staticmethod
    def _validate_spectrum_and_emission(
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Comprueba la coherencia entre espectro y emisión.
        """

        if candidate.has_emission and not candidate.has_spectrum:
            result.add_warning(
                code="EMISSION_WITHOUT_SPECTRUM",
                message=(
                    "Se indica presencia de emisión, pero no hay espectro "
                    "disponible."
                ),
                field_name="has_emission",
                value=candidate.has_emission,
            )

        if candidate.has_spectrum:
            result.add_info(
                code="SPECTRUM_AVAILABLE",
                message="El candidato dispone de espectro.",
                field_name="has_spectrum",
                value=True,
            )

    @staticmethod
    def _add_classification_information(
        candidate: StarCandidate,
        result: ValidationResult,
    ) -> None:
        """
        Registra información sobre la clasificación externa.
        """

        if candidate.object_class is None:
            result.add_info(
                code="MISSING_EXTERNAL_CLASSIFICATION",
                message=(
                    "El candidato no tiene una clasificación externa "
                    "asociada."
                ),
                field_name="object_class",
            )
            return

        result.add_info(
            code="EXTERNAL_CLASSIFICATION_AVAILABLE",
            message="El candidato tiene una clasificación externa.",
            field_name="object_class",
            value=candidate.object_class,
        )