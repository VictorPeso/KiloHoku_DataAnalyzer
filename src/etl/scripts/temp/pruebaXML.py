from etl.database import dispose_engine
from etl.extractors.files import VOTableExtractor
from etl.loaders import LightCurvePostgresLoader
from etl.logger import configure_logging


def main() -> None:
    configure_logging()

    extractor = VOTableExtractor(
        source_path="ZTF17aaaacsm_g.xml",
        search_right_ascension=79.299,
        search_declination=7.0399,
        search_radius_degrees=0.0014,
    )

    try:
        curves = extractor.extract()

        loader = LightCurvePostgresLoader()

        result = loader.load(
            alert_id="ZTF17aaaacsm",
            light_curves=curves,
        )

        print(
            result.alert_id,
            result.processed_curves,
            result.inserted_curves,
            result.updated_curves,
            result.stored_observations,
        )

    finally:
        dispose_engine()


if __name__ == "__main__":
    main()