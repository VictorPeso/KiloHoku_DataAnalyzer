from etl.database import (
    dispose_engine,
    recreate_database_schema,
)
from etl.logger import configure_logging


def main() -> None:
    configure_logging()

    try:
        recreate_database_schema()
    finally:
        dispose_engine()


if __name__ == "__main__":
    main()