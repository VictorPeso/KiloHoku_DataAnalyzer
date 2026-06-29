"""
Punto de entrada temporal para probar la pipeline de importación
de candidatos estelares.
"""

from __future__ import annotations

from etl.config import settings
from etl.extractors.files import CsvExtractor
from etl.logger import configure_logging, get_logger
from etl.pipelines import ImportStarCandidatesPipeline
from etl.transformers import StarCandidateTransformer


logger = get_logger(__name__)


def main() -> None:
    """
    Ejecuta la pipeline de importación de resultados.csv.
    """
    logger.info(
        "----------------------------------------------------------------"
    )

    configure_logging()

    csv_path = settings.project_root / "resultados.csv"

    logger.info(
        "Iniciando aplicación ETL. source=%s",
        csv_path,
    )

    try:
        extractor = CsvExtractor(csv_path)
        transformer = StarCandidateTransformer()

        pipeline = ImportStarCandidatesPipeline(
            extractor=extractor,
            transformer=transformer,
        )

        result = pipeline.run(
            skip_invalid_rows=False,
        )

        first_candidate = result.candidates[0]

        logger.info(
            "Ejecución completada correctamente. "
            "candidates=%d first_alert_id=%s success_rate=%.2f",
            result.valid_rows,
            first_candidate.alert_id,
            result.success_rate,
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