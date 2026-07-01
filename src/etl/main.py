"""
Punto de entrada principal de la aplicación ETL.
"""

from __future__ import annotations

from etl.scripts.import_candidates_from_csv import main as run_csv_import


def main() -> None:
    """
    Ejecuta la importación de candidatos desde resultados.csv.
    """

    run_csv_import()


if __name__ == "__main__":
    main()