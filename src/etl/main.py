"""
Prueba completa del proceso ETL:

Extract → Transform → Validate → Load → PostgreSQL
"""

from __future__ import annotations

from etl.config import settings
from etl.database import (
    check_database_connection,
    create_database_schema,
    dispose_engine,
    read_only_session_scope,
)
from etl.database.repositories import StarCandidateRepository
from etl.extractors.files import CsvExtractor
from etl.loaders import PostgresLoader
from etl.logger import configure_logging, get_logger
from etl.pipelines import ImportStarCandidatesPipeline
from etl.transformers import StarCandidateTransformer
from etl.validators import (
    StarCandidateValidationConfig,
    StarCandidateValidator,
)


logger = get_logger(__name__)


def verify_database_contents(
    expected_count: int,
) -> None:
    """
    Comprueba que los candidatos se hayan almacenado correctamente.
    """

    with read_only_session_scope() as session:
        repository = StarCandidateRepository(session)

        stored_count = repository.count()

        logger.info(
            "Verificando registros almacenados. expected=%d stored=%d",
            expected_count,
            stored_count,
        )

        if stored_count != expected_count:
            raise RuntimeError(
                "El número de registros almacenados no coincide con el "
                f"esperado. expected={expected_count}, stored={stored_count}"
            )

        first_models = repository.list_all(limit=1)

        if not first_models:
            raise RuntimeError(
                "La tabla existe, pero no contiene ningún candidato."
            )

        first_model = first_models[0]

        logger.info(
            "Primer registro recuperado correctamente. "
            "database_id=%s alert_id=%s gaia_dr3_name=%s",
            first_model.id,
            first_model.alert_id,
            first_model.gaia_dr3_name,
        )


def main() -> None:
    """
    Ejecuta y verifica el proceso ETL completo.
    """

    configure_logging()
    
    logger.info(
        "------------------------------------------------"
    )
    csv_path = settings.project_root / "resultados.csv"

    logger.info(
        "Iniciando prueba completa del ETL. source=%s",
        csv_path,
    )

    try:
        # Comprueba que PostgreSQL esté disponible.
        check_database_connection()

        # Crea la tabla si todavía no existe.
        create_database_schema()

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

        # False: un error de transformación detiene la pipeline.
        # True: un candidato inválido se separa, pero el proceso continúa.
        pipeline_result = pipeline.run(
            skip_invalid_transformation_rows=False,
            skip_invalid_validation_candidates=True,
        )

        logger.info(
            "Datos preparados para persistencia. "
            "extracted=%d transformed=%d valid=%d invalid=%d",
            pipeline_result.extracted_rows,
            pipeline_result.transformed_rows,
            pipeline_result.validation_valid_rows,
            pipeline_result.validation_invalid_rows,
        )

        loader = PostgresLoader()

        load_result = loader.load(
            pipeline_result.valid_candidates
        )

        logger.info(
            "Carga finalizada. processed=%d inserted=%d updated=%d",
            load_result.processed,
            load_result.inserted,
            load_result.updated,
        )

        verify_database_contents(
            expected_count=pipeline_result.validation_valid_rows,
        )

        logger.info(
            "Prueba completa finalizada satisfactoriamente."
        )

    except Exception:
        logger.exception(
            "La prueba completa del ETL ha fallado."
        )
        raise

    finally:
        dispose_engine()
        logger.info("Aplicación ETL finalizada.")


if __name__ == "__main__":
    main()