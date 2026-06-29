"""
Punto de entrada temporal para probar la pipeline completa de candidatos.
"""

from __future__ import annotations

from etl.config import settings
from etl.extractors.files import CsvExtractor
from etl.logger import configure_logging, get_logger
from etl.pipelines import ImportStarCandidatesPipeline
from etl.transformers import StarCandidateTransformer
from etl.validators import (
    StarCandidateValidationConfig,
    StarCandidateValidator,
)


logger = get_logger(__name__)


def main() -> None:
    """
    Ejecuta la pipeline de extracción, transformación y validación.
    """

    configure_logging()

    logger.info(
        "----------------------------------------------------------------"
    )

    csv_path = settings.project_root / "resultados.csv"

    logger.info(
        "Iniciando aplicación ETL. source=%s",
        csv_path,
    )

    try:
        extractor = CsvExtractor(csv_path)
        transformer = StarCandidateTransformer()

        validation_config = StarCandidateValidationConfig(
            maximum_angular_distance=5.0,
            maximum_parallax_relative_error=1.0,
            minimum_gaia_magnitude=-5.0,
            maximum_gaia_magnitude=30.0,
            maximum_color_index=10.0,
            require_generated_resources=False,
            require_simbad_match=False,
        )

        validator = StarCandidateValidator(
            config=validation_config,
        )

        pipeline = ImportStarCandidatesPipeline(
            extractor=extractor,
            transformer=transformer,
            validator=validator,
        )

        result = pipeline.run(
            skip_invalid_transformation_rows=False,
            skip_invalid_validation_candidates=True,
        )
        """
        skip_invalid_transformation_rows:
        # Si es False, la primera fila que no pueda transformarse detendrá la pipeline.
        # Si es True, las filas con errores de transformación se omitirán y el proceso continuará.

        skip_invalid_validation_candidates:
        # Si es False, el primer candidato que no supere la validación detendrá la pipeline.
        # Si es True, los candidatos inválidos se separarán en result.invalid_candidates y la ejecución continuará con el resto.
        """

        logger.info(
            "Ejecución completada. extracted=%d transformed=%d "
            "valid=%d invalid=%d warnings=%d",
            result.extracted_rows,
            result.transformed_rows,
            result.validation_valid_rows,
            result.validation_invalid_rows,
            result.validation_warning_count,
        )

        if result.valid_candidates:
            logger.info(
                "Primer candidato válido. alert_id=%s",
                result.valid_candidates[0].alert_id,
            )

        if result.invalid_candidates:
            logger.warning(
                "La ejecución contiene candidatos inválidos. count=%d",
                len(result.invalid_candidates),
            )

    except Exception:
        logger.exception(
            "La aplicación ETL ha finalizado debido a un error."
        )
        raise

    finally:
        logger.info("Aplicación ETL finalizada.")


if __name__ == "__main__":
    main()