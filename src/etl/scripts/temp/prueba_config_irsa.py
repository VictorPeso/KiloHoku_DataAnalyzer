from etl.config import settings


def main() -> None:

    print(
        settings.irsa_search_radius_degrees,
        type(settings.irsa_search_radius_degrees),
    )
    
    print(
        "IRSA search radius degrees:",
        settings.irsa_search_radius_degrees,
    )

    print(
        "IRSA search radius arcseconds:",
        settings.irsa_search_radius_arcseconds,
    )

    print(
        "IRSA minimum observations:",
        settings.irsa_minimum_observations,
    )

    print(
        "IRSA bad catalog flags mask:",
        settings.irsa_bad_catalog_flags_mask,
    )

    print(
        "IRSA request timeout seconds:",
        settings.irsa_request_timeout_seconds,
    )

    print(
        "IRSA request delay seconds:",
        settings.irsa_request_delay_seconds,
    )

    print(
        "IRSA max retries:",
        settings.irsa_max_retries,
    )


if __name__ == "__main__":
    main()