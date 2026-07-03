from pathlib import Path

from etl.config import settings
from etl.database import (
    dispose_engine,
    read_only_session_scope,
)
from etl.database.repositories import StarCandidateRepository
from etl.domain.value_objects import PhotometricBand
from etl.extractors.api import (
    IrsaClient,
    IrsaLightCurveQuery,
)
from etl.extractors.files import VOTableExtractor
from etl.loaders import LightCurvePostgresLoader
from etl.logger import configure_logging


ALERT_ID = "ZTF17aaajocf"


def main() -> None:
    configure_logging()

    try:
        with read_only_session_scope() as session:
            repository = StarCandidateRepository(session)

            candidate = repository.get_by_alert_id(ALERT_ID)

            if candidate is None:
                raise RuntimeError(
                    f"No existe el candidato {ALERT_ID!r}."
                )

            candidate_ra = candidate.right_ascension
            candidate_dec = candidate.declination

        query = IrsaLightCurveQuery(
            right_ascension=candidate_ra,
            declination=candidate_dec,
            radius_degrees=settings.irsa_search_radius_degrees,
            band=PhotometricBand.G,
            minimum_observations=(
                settings.irsa_minimum_observations
            ),
        )

        client = IrsaClient()

        votable_content = client.download_light_curves(query)

        temporary_path = (
            settings.project_root
            / "data"
            / "temp"
            / f"{ALERT_ID}_g.xml"
        )

        temporary_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path.write_bytes(votable_content)

        extractor = VOTableExtractor(
            source_path=temporary_path,
            search_right_ascension=candidate_ra,
            search_declination=candidate_dec,
            search_radius_degrees=(
                settings.irsa_search_radius_degrees
            ),
        )

        curves = extractor.extract()

        print(
            f"Respuesta descargada: {temporary_path}"
        )
        print(
            f"Curvas encontradas: {len(curves)}"
        )

        for curve in curves:
            print(
                curve.curve_key,
                curve.observation_count,
                curve.mean_magnitude,
            )

        loader = LightCurvePostgresLoader()

        load_result = loader.load(
            alert_id=ALERT_ID,
            light_curves=curves,
        )

        print(
            "Carga:",
            load_result.processed_curves,
            load_result.inserted_curves,
            load_result.updated_curves,
            load_result.stored_observations,
        )

    finally:
        dispose_engine()


if __name__ == "__main__":
    main()