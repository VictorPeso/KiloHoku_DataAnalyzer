"""
Script para importar candidatos estelares desde un archivo CSV.

El proceso ejecutado es:

    CSV
      ↓
    extracción
      ↓
    transformación
      ↓
    validación
      ↓
    carga en PostgreSQL

Este script puede ejecutarse directamente cuando sea necesario:

    python -m etl.scripts.import_candidates_from_csv
"""

from __future__ import annotations

from pathlib import Path

from etl.config import settings
from etl.database import (
    check_database_connection,
    create_database_schema,
    dispose_engine,
)
from etl.extractors.files import CsvExtractor
from etl.loaders import PostgresLoader, PostgresLoadResult
from etl.logger import configure_logging, get_logger
from etl.pipelines import ImportStarCandidatesPipeline
from etl.transformers import StarCandidateTransformer
from etl.validators import (
    StarCandidateValidationConfig,
    StarCandidateValidator,
)


logger = get_logger(__name__)


def import_candidates_from_csv(
    csv_path: str | Path,
) -> PostgresLoadResult:
    """
    Importa candidatos estelares desde un archivo CSV.

    Args:
        csv_path:
            Ruta del archivo CSV que debe procesarse.

    Returns:
        Resultado de la carga en PostgreSQL.

    Raises:
        Exception:
            Propaga cualquier error de extracción, transformación,
            validación o persistencia.
    """

    source_path = Path(csv_path).expanduser().resolve()

    logger.info(
        "Iniciando importación de candidatos desde CSV. source=%s",
        source_path,
    )

    check_database_connection()
    create_database_schema()

    extractor = CsvExtractor(source_path)
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

    # False: una fila que no pueda transformarse detendrá la ejecución.
    # True: un candidato que no supere la validación se omitirá y el
    # proceso continuará con los demás candidatos.
    pipeline_result = pipeline.run(
        skip_invalid_transformation_rows=False,
        skip_invalid_validation_candidates=True,
    )

    loader = PostgresLoader()

    load_result = loader.load(
        pipeline_result.valid_candidates
    )

    logger.info(
        "Importación desde CSV completada. "
        "extracted=%d transformed=%d valid=%d invalid=%d "
        "processed=%d inserted=%d updated=%d",
        pipeline_result.extracted_rows,
        pipeline_result.transformed_rows,
        pipeline_result.validation_valid_rows,
        pipeline_result.validation_invalid_rows,
        load_result.processed,
        load_result.inserted,
        load_result.updated,
    )

    return load_result


def main() -> None:
    """
    Ejecuta la importación utilizando resultados.csv.
    """

    configure_logging()

    csv_path = settings.project_root / "resultados.csv"

    try:
        import_candidates_from_csv(csv_path)

    except Exception:
        logger.exception(
            "La importación de candidatos desde CSV ha fallado."
        )
        raise

    finally:
        dispose_engine()
        logger.info(
            "Script de importación desde CSV finalizado."
        )


if __name__ == "__main__":
    main()