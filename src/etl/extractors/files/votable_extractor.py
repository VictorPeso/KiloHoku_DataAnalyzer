"""
Extractor de curvas de luz desde archivos VOTable XML.

Este extractor interpreta los VOTable devueltos por el servicio de curvas
de luz ZTF de NASA/IPAC y los transforma en entidades de dominio.

El proceso realizado es:

    archivo XML VOTable
        ↓
    lectura de FIELD y TABLEDATA
        ↓
    conversión de cada fila en LightCurveObservation
        ↓
    agrupación por oid y filtercode
        ↓
    creación de una o varias entidades LightCurve

Una misma consulta posicional puede devolver varios objetos ZTF. Por ello,
el extractor devuelve una lista de curvas y no una única LightCurve.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import mean
from xml.etree import ElementTree

from etl.domain.entities import (
    LightCurve,
    LightCurveObservation,
)
from etl.domain.value_objects import PhotometricBand
from etl.extractors.base import BaseExtractor
from etl.extractors.exceptions import (
    ExtractionError,
    InvalidVOTableError,
    SourceFileNotFoundError,
    VOTableRowError,
)
from etl.logger import get_logger


logger = get_logger(__name__)


class VOTableExtractor(BaseExtractor[list[LightCurve]]):
    """
    Extrae curvas de luz desde un archivo VOTable XML.

    La ascensión recta, declinación y radio de búsqueda no siempre aparecen
    como parámetros dentro del XML. Por eso deben proporcionarse al crear el
    extractor.

    Example:
        extractor = VOTableExtractor(
            source_path="ZTF17aaaacsm_g.xml",
            search_right_ascension=79.299,
            search_declination=7.0399,
            search_radius_degrees=0.0014,
        )

        curves = extractor.extract()
    """

    REQUIRED_FIELDS = frozenset(
        {
            "oid",
            "expid",
            "hjd",
            "mjd",
            "mag",
            "magerr",
            "catflags",
            "filtercode",
            "ra",
            "dec",
        }
    )

    def __init__(
        self,
        source_path: str | Path,
        *,
        search_right_ascension: float,
        search_declination: float,
        search_radius_degrees: float,
    ) -> None:
        """
        Inicializa el extractor.

        Args:
            source_path:
                Ruta del archivo VOTable XML.

            search_right_ascension:
                Ascensión recta usada en la consulta a IRSA.

            search_declination:
                Declinación usada en la consulta a IRSA.

            search_radius_degrees:
                Radio de búsqueda usado en la consulta, en grados.
        """

        self._source_path = Path(source_path).expanduser().resolve()
        self._search_right_ascension = float(
            search_right_ascension
        )
        self._search_declination = float(search_declination)
        self._search_radius_degrees = float(
            search_radius_degrees
        )

        self._validate_search_parameters()

    @property
    def source_path(self) -> Path:
        """
        Devuelve la ruta del VOTable.
        """

        return self._source_path

    def extract(self) -> list[LightCurve]:
        """
        Lee el VOTable y construye las curvas de luz.

        Returns:
            Lista de curvas agrupadas por objeto ZTF y banda.

        Raises:
            SourceFileNotFoundError:
                Si el archivo no existe.

            InvalidVOTableError:
                Si el XML no es válido o le faltan campos obligatorios.

            VOTableRowError:
                Si una fila no puede convertirse.
        """

        self._validate_source_file()

        logger.info(
            "Iniciando extracción de VOTable. source=%s",
            self._source_path,
        )

        root = self._parse_xml()
        table = self._find_table(root)

        field_names = self._extract_field_names(table)
        self._validate_required_fields(field_names)

        rows = self._extract_rows(
            table=table,
            field_names=field_names,
        )

        curves = self._build_light_curves(rows)

        logger.info(
            "Extracción de VOTable completada. source=%s "
            "rows=%d curves=%d",
            self._source_path,
            len(rows),
            len(curves),
        )

        return curves

    def _validate_source_file(self) -> None:
        """
        Comprueba que el archivo existe y es accesible.
        """

        if not self._source_path.exists():
            raise SourceFileNotFoundError(
                f"No existe el archivo VOTable: "
                f"{self._source_path}"
            )

        if not self._source_path.is_file():
            raise SourceFileNotFoundError(
                f"La ruta del VOTable no corresponde a un archivo: "
                f"{self._source_path}"
            )

    def _parse_xml(self) -> ElementTree.Element:
        """
        Interpreta el documento XML.

        Returns:
            Elemento raíz del documento.
        """

        try:
            tree = ElementTree.parse(self._source_path)
        except ElementTree.ParseError as error:
            raise InvalidVOTableError(
                f"El archivo no contiene un XML válido: "
                f"{self._source_path}"
            ) from error
        except OSError as error:
            raise ExtractionError(
                f"No se pudo leer el archivo VOTable: "
                f"{self._source_path}"
            ) from error

        root = tree.getroot()

        if self._local_name(root.tag) != "VOTABLE":
            raise InvalidVOTableError(
                "El elemento raíz del archivo debe ser VOTABLE."
            )

        return root

    def _find_table(
        self,
        root: ElementTree.Element,
    ) -> ElementTree.Element:
        """
        Localiza la primera tabla del VOTable.
        """

        table = next(
            (
                element
                for element in root.iter()
                if self._local_name(element.tag) == "TABLE"
            ),
            None,
        )

        if table is None:
            raise InvalidVOTableError(
                "El VOTable no contiene ningún elemento TABLE."
            )

        return table

    def _extract_field_names(
        self,
        table: ElementTree.Element,
    ) -> list[str]:
        """
        Obtiene los nombres de las columnas respetando su orden.
        """

        field_names: list[str] = []

        for child in table:
            if self._local_name(child.tag) != "FIELD":
                continue

            raw_name = child.attrib.get("name")

            if raw_name is None or not raw_name.strip():
                raise InvalidVOTableError(
                    "Se ha encontrado un FIELD sin atributo name."
                )

            field_names.append(raw_name.strip().lower())

        if not field_names:
            raise InvalidVOTableError(
                "El VOTable no contiene definiciones FIELD."
            )

        if len(field_names) != len(set(field_names)):
            raise InvalidVOTableError(
                "El VOTable contiene nombres de columnas duplicados."
            )

        return field_names

    def _validate_required_fields(
        self,
        field_names: list[str],
    ) -> None:
        """
        Comprueba que estén disponibles las columnas mínimas.
        """

        missing_fields = sorted(
            self.REQUIRED_FIELDS.difference(field_names)
        )

        if missing_fields:
            raise InvalidVOTableError(
                "Faltan campos obligatorios en el VOTable: "
                f"{', '.join(missing_fields)}."
            )

    def _extract_rows(
        self,
        *,
        table: ElementTree.Element,
        field_names: list[str],
    ) -> list[dict[str, str | None]]:
        """
        Extrae las filas TABLEDATA como diccionarios.
        """

        table_data = next(
            (
                element
                for element in table.iter()
                if self._local_name(element.tag) == "TABLEDATA"
            ),
            None,
        )

        if table_data is None:
            raise InvalidVOTableError(
                "El VOTable no contiene una sección TABLEDATA."
            )

        rows: list[dict[str, str | None]] = []

        for row_index, table_row in enumerate(
            (
                element
                for element in table_data
                if self._local_name(element.tag) == "TR"
            ),
            start=1,
        ):
            values = [
                self._normalize_cell_text(cell.text)
                for cell in table_row
                if self._local_name(cell.tag) == "TD"
            ]

            if len(values) != len(field_names):
                raise InvalidVOTableError(
                    "El número de celdas no coincide con el número "
                    f"de campos en la fila {row_index}. "
                    f"Campos: {len(field_names)}. "
                    f"Celdas: {len(values)}."
                )

            rows.append(dict(zip(field_names, values, strict=True)))

        if not rows:
            logger.warning(
                "El VOTable no contiene observaciones. source=%s",
                self._source_path,
            )

        return rows

    def _build_light_curves(
        self,
        rows: list[dict[str, str | None]],
    ) -> list[LightCurve]:
        """
        Agrupa las filas por objeto ZTF y banda.
        """

        grouped_rows: defaultdict[
            tuple[int, PhotometricBand],
            list[dict[str, str | None]],
        ] = defaultdict(list)

        for row_index, row in enumerate(rows, start=1):
            try:
                ztf_object_id = self._parse_required_integer(
                    row,
                    "oid",
                )

                band = PhotometricBand.from_ztf_filter_code(
                    self._parse_required_string(
                        row,
                        "filtercode",
                    )
                )
            except (TypeError, ValueError) as error:
                raise VOTableRowError(
                    "No se pudo identificar el objeto o la banda "
                    f"de la fila {row_index}."
                ) from error

            grouped_rows[(ztf_object_id, band)].append(row)

        curves: list[LightCurve] = []

        for (ztf_object_id, band), curve_rows in grouped_rows.items():
            observations = tuple(
                self._build_observation(
                    row,
                    row_index=row_index,
                )
                for row_index, row in enumerate(
                    curve_rows,
                    start=1,
                )
            )

            source_right_ascension = mean(
                observation.right_ascension
                for observation in observations
            )

            source_declination = mean(
                observation.declination
                for observation in observations
            )

            curves.append(
                LightCurve(
                    ztf_object_id=ztf_object_id,
                    band=band,
                    source_right_ascension=(
                        source_right_ascension
                    ),
                    source_declination=source_declination,
                    search_right_ascension=(
                        self._search_right_ascension
                    ),
                    search_declination=(
                        self._search_declination
                    ),
                    search_radius_degrees=(
                        self._search_radius_degrees
                    ),
                    observations=observations,
                )
            )

        return sorted(
            curves,
            key=lambda curve: (
                curve.ztf_object_id,
                curve.band.value,
            ),
        )

    def _build_observation(
        self,
        row: Mapping[str, str | None],
        *,
        row_index: int,
    ) -> LightCurveObservation:
        """
        Convierte una fila del VOTable en una observación.
        """

        try:
            return LightCurveObservation(
                exposure_id=self._parse_required_integer(
                    row,
                    "expid",
                ),
                heliocentric_julian_date=(
                    self._parse_required_float(row, "hjd")
                ),
                modified_julian_date=(
                    self._parse_required_float(row, "mjd")
                ),
                magnitude=self._parse_required_float(
                    row,
                    "mag",
                ),
                magnitude_error=self._parse_required_float(
                    row,
                    "magerr",
                ),
                catalog_flags=self._parse_required_integer(
                    row,
                    "catflags",
                ),
                right_ascension=self._parse_required_float(
                    row,
                    "ra",
                ),
                declination=self._parse_required_float(
                    row,
                    "dec",
                ),
                chi=self._parse_optional_float(row, "chi"),
                sharpness=self._parse_optional_float(
                    row,
                    "sharp",
                ),
                file_fraction_day=self._parse_optional_integer(
                    row,
                    "filefracday",
                ),
                field_id=self._parse_optional_integer(
                    row,
                    "field",
                ),
                ccd_id=self._parse_optional_integer(
                    row,
                    "ccdid",
                ),
                quadrant_id=self._parse_optional_integer(
                    row,
                    "qid",
                ),
                limiting_magnitude=self._parse_optional_float(
                    row,
                    "limitmag",
                ),
                magnitude_zero_point=self._parse_optional_float(
                    row,
                    "magzp",
                ),
                magnitude_zero_point_rms=(
                    self._parse_optional_float(
                        row,
                        "magzprms",
                    )
                ),
                color_coefficient=self._parse_optional_float(
                    row,
                    "clrcoeff",
                ),
                color_coefficient_error=(
                    self._parse_optional_float(
                        row,
                        "clrcounc",
                    )
                ),
                exposure_time=self._parse_optional_float(
                    row,
                    "exptime",
                ),
                airmass=self._parse_optional_float(
                    row,
                    "airmass",
                ),
                program_id=self._parse_optional_integer(
                    row,
                    "programid",
                ),
            )

        except (TypeError, ValueError) as error:
            raise VOTableRowError(
                f"No se pudo convertir la fila {row_index} "
                "en una observación válida."
            ) from error

    @staticmethod
    def _parse_required_string(
        row: Mapping[str, str | None],
        field_name: str,
    ) -> str:
        """
        Obtiene un string obligatorio.
        """

        value = row.get(field_name)

        if value is None or not value.strip():
            raise ValueError(
                f"El campo {field_name} es obligatorio."
            )

        return value.strip()

    @classmethod
    def _parse_required_integer(
        cls,
        row: Mapping[str, str | None],
        field_name: str,
    ) -> int:
        """
        Convierte un entero obligatorio.

        Se utiliza base cero para admitir valores decimales y
        representaciones hexadecimales como ``0x10``.
        """

        value = cls._parse_required_string(row, field_name)

        try:
            return int(value, base=0)
        except ValueError as error:
            raise ValueError(
                f"El campo {field_name} no contiene un entero "
                f"válido: {value!r}."
            ) from error

    @classmethod
    def _parse_optional_integer(
        cls,
        row: Mapping[str, str | None],
        field_name: str,
    ) -> int | None:
        """
        Convierte un entero opcional.
        """

        value = row.get(field_name)

        if value is None or not value.strip():
            return None

        try:
            return int(value.strip(), base=0)
        except ValueError as error:
            raise ValueError(
                f"El campo {field_name} no contiene un entero "
                f"válido: {value!r}."
            ) from error

    @classmethod
    def _parse_required_float(
        cls,
        row: Mapping[str, str | None],
        field_name: str,
    ) -> float:
        """
        Convierte un número real obligatorio.
        """

        value = cls._parse_required_string(row, field_name)

        try:
            return float(value)
        except ValueError as error:
            raise ValueError(
                f"El campo {field_name} no contiene un número "
                f"válido: {value!r}."
            ) from error

    @staticmethod
    def _parse_optional_float(
        row: Mapping[str, str | None],
        field_name: str,
    ) -> float | None:
        """
        Convierte un número real opcional.
        """

        value = row.get(field_name)

        if value is None or not value.strip():
            return None

        try:
            return float(value.strip())
        except ValueError as error:
            raise ValueError(
                f"El campo {field_name} no contiene un número "
                f"válido: {value!r}."
            ) from error

    @staticmethod
    def _normalize_cell_text(
        value: str | None,
    ) -> str | None:
        """
        Normaliza el contenido de una celda TD.
        """

        if value is None:
            return None

        normalized_value = value.strip()

        return normalized_value or None

    @staticmethod
    def _local_name(tag: str) -> str:
        """
        Elimina el namespace XML de una etiqueta.

        Por ejemplo:

            {http://www.ivoa.net/xml/VOTable/v1.3}TABLE

        se convierte en:

            TABLE
        """

        return tag.rsplit("}", maxsplit=1)[-1]

    def _validate_search_parameters(self) -> None:
        """
        Valida los parámetros de la consulta original.
        """

        if not 0.0 <= self._search_right_ascension < 360.0:
            raise ValueError(
                "search_right_ascension debe estar entre "
                "0, inclusive, y 360, exclusive."
            )

        if not -90.0 <= self._search_declination <= 90.0:
            raise ValueError(
                "search_declination debe estar entre -90 y 90."
            )

        if self._search_radius_degrees <= 0.0:
            raise ValueError(
                "search_radius_degrees debe ser mayor que cero."
            )