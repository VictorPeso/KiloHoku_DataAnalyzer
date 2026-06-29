Para tu caso —un **módulo Python independiente**, ejecutado en su propio contenedor, que extrae datos de APIs/archivos, los procesa y los guarda en PostgreSQL— usaría una arquitectura por capas, separando claramente:

**Extract → Transform → Validate → Load**

Además, como este módulo será el responsable de escribir en la base de datos, también debería ser el propietario de las migraciones y del esquema.

## Estructura recomendada

```text
data-processor/
│
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── Dockerfile
├── compose.yaml
├── alembic.ini
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_create_stars.py
│       ├── 002_create_light_curves.py
│       └── ...
│
├── src/
│   └── data_processor/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── logging_config.py
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── entities/
│       │   │   ├── star.py
│       │   │   ├── light_curve.py
│       │   │   └── classification.py
│       │   │
│       │   ├── value_objects/
│       │   │   ├── coordinates.py
│       │   │   └── magnitude.py
│       │   │
│       │   └── exceptions.py
│       │
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── api/
│       │   │   ├── client.py
│       │   │   ├── stars_api.py
│       │   │   └── schemas.py
│       │   │
│       │   └── files/
│       │       ├── xml_extractor.py
│       │       ├── csv_extractor.py
│       │       └── fits_extractor.py
│       │
│       ├── transformers/
│       │   ├── __init__.py
│       │   ├── light_curve_transformer.py
│       │   ├── star_transformer.py
│       │   ├── normalization.py
│       │   └── feature_engineering.py
│       │
│       ├── validators/
│       │   ├── __init__.py
│       │   ├── star_validator.py
│       │   ├── light_curve_validator.py
│       │   └── validation_result.py
│       │
│       ├── loaders/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── postgres_loader.py
│       │
│       ├── pipelines/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── import_stars_pipeline.py
│       │   ├── import_light_curves_pipeline.py
│       │   └── classify_stars_pipeline.py
│       │
│       ├── database/
│       │   ├── __init__.py
│       │   ├── session.py
│       │   ├── models/
│       │   │   ├── star_model.py
│       │   │   ├── light_curve_model.py
│       │   │   └── classification_model.py
│       │   │
│       │   └── repositories/
│       │       ├── star_repository.py
│       │       ├── light_curve_repository.py
│       │       └── classification_repository.py
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── classification_service.py
│       │   ├── curve_analysis_service.py
│       │   └── import_service.py
│       │
│       ├── jobs/
│       │   ├── __init__.py
│       │   ├── scheduled_import.py
│       │   └── classify_pending.py
│       │
│       └── cli/
│           ├── __init__.py
│           └── commands.py
│
├── tests/
│   ├── unit/
│   │   ├── extractors/
│   │   ├── transformers/
│   │   ├── validators/
│   │   └── services/
│   │
│   ├── integration/
│   │   ├── database/
│   │   ├── api/
│   │   └── pipelines/
│   │
│   ├── fixtures/
│   │   ├── sample.xml
│   │   ├── sample.csv
│   │   └── api_responses/
│   │
│   └── conftest.py
│
├── scripts/
│   ├── run_import.py
│   ├── run_classification.py
│   └── seed_database.py
│
└── docs/
    ├── architecture.md
    ├── database.md
    └── pipelines.md
```

## Responsabilidad de cada capa

### `extractors/`

Contiene todo lo relacionado con la obtención de datos.

```text
extractors/
├── api/
└── files/
```

Por ejemplo:

```python
class StarsApiExtractor:
    def extract(self) -> list[dict]:
        ...
```

El extractor debería devolver datos crudos o muy cercanos a la respuesta original. No debería realizar cálculos científicos complejos ni guardar datos en la base de datos.

---

### `transformers/`

Convierte los datos externos al formato interno de la aplicación.

Aquí se harían tareas como:

- Cambiar nombres de campos.
- Convertir fechas.
- Convertir strings a números.
- Normalizar magnitudes.
- Eliminar valores inválidos.
- Calcular características de una curva de luz.
- Preparar datos para clasificación.

Ejemplo:

```python
class LightCurveTransformer:
    def transform(self, raw_data: dict) -> LightCurve:
        ...
```

El resultado idealmente debería ser una entidad del dominio, no todavía un modelo SQLAlchemy.

---

### `validators/`

Aunque a veces se incluye dentro de `transformers`, considero mejor separarlo.

La validación responde preguntas como:

- ¿Faltan campos obligatorios?
- ¿La curva tiene suficientes observaciones?
- ¿Las magnitudes son numéricas?
- ¿Los tiempos están ordenados?
- ¿Las coordenadas están dentro de rangos válidos?

```python
class LightCurveValidator:
    def validate(self, curve: LightCurve) -> ValidationResult:
        ...
```

De esta forma puedes distinguir entre:

- Datos técnicamente inválidos.
- Datos válidos pero incompletos.
- Datos válidos y procesables.

---

### `loaders/`

Se encarga de cargar el resultado procesado.

```python
class PostgresLoader:
    def load(self, curves: list[LightCurve]) -> None:
        ...
```

En un proyecto pequeño, el loader podría utilizar directamente los repositorios. En un proyecto más escalable, el loader coordina la persistencia de varias entidades dentro de una transacción.

---

### `pipelines/`

Es la parte que orquesta el ETL completo.

Por ejemplo:

```python
class ImportLightCurvesPipeline:
    def __init__(
        self,
        extractor,
        transformer,
        validator,
        loader,
    ):
        self.extractor = extractor
        self.transformer = transformer
        self.validator = validator
        self.loader = loader

    def run(self) -> None:
        raw_items = self.extractor.extract()

        valid_curves = []

        for raw_item in raw_items:
            curve = self.transformer.transform(raw_item)
            result = self.validator.validate(curve)

            if result.is_valid:
                valid_curves.append(curve)

        self.loader.load(valid_curves)
```

Esta clase no debería contener la implementación detallada de los cálculos. Solo coordina los pasos.

## Diferencia entre `pipelines` y `services`

Puede parecer que hacen lo mismo, pero conviene diferenciarlos.

### Pipeline

Representa un flujo de trabajo completo:

```text
API → transformación → validación → PostgreSQL
```

Por ejemplo:

```text
ImportLightCurvesPipeline
ClassifyPendingStarsPipeline
ReprocessLightCurvesPipeline
```

### Service

Representa una operación del dominio:

```text
calcular periodo
normalizar curva
clasificar estrella
calcular características
```

Por ejemplo:

```python
classification_service.classify(curve)
curve_analysis_service.calculate_period(curve)
```

El pipeline utiliza los servicios para ejecutar la lógica científica o de negocio.

## `domain/`: modelos internos

Aquí colocarías las representaciones propias del problema.

```python
@dataclass
class LightCurve:
    star_id: str
    time: list[float]
    magnitude: list[float]
    filter_name: str | None = None
```

Estas entidades no deberían depender de PostgreSQL, SQLAlchemy ni de la API externa.

Eso permite utilizar el mismo objeto para:

- Procesar datos.
- Ejecutar tests.
- Exportar resultados.
- Clasificar estrellas.
- Guardar en distintas bases de datos.

## `database/models/`: modelos SQLAlchemy

Los modelos de base de datos deberían estar separados de las entidades del dominio.

```python
class LightCurveModel(Base):
    __tablename__ = "light_curves"

    id = mapped_column(UUID, primary_key=True)
    star_id = mapped_column(ForeignKey("stars.id"))
    filter_name = mapped_column(String)
```

La separación sería:

```text
LightCurve          → entidad del dominio
LightCurveModel     → representación de PostgreSQL
```

Esto evita que todo el código científico dependa de SQLAlchemy.

## `repositories/`

Los repositorios encapsulan las consultas a la base de datos.

```python
class StarRepository:
    def find_by_external_id(self, external_id: str) -> StarModel | None:
        ...

    def save(self, star: Star) -> StarModel:
        ...

    def find_pending_classification(self) -> list[StarModel]:
        ...
```

Así los servicios y pipelines no contienen consultas SQL directamente.

## Flujo recomendado

En tu proyecto, el flujo podría ser:

```mermaid
flowchart LR
    A[API o archivo XML] --> B[Extractor]
    B --> C[Transformer]
    C --> D[Validator]
    D --> E[Servicios de análisis]
    E --> F[Loader]
    F --> G[Repositories]
    G --> H[(PostgreSQL)]
    H --> I[Backend REST]
    I --> J[Frontend]
```

El backend REST no debería ejecutar este procesamiento. Solo debería consultar los resultados ya persistidos.

## Varias pipelines en lugar de una sola

Evitaría crear una única clase ETL gigantesca. Es preferible tener varias pipelines según el caso de uso.

```text
pipelines/
├── import_catalog_pipeline.py
├── import_light_curves_pipeline.py
├── process_pending_curves_pipeline.py
├── classify_stars_pipeline.py
└── export_results_pipeline.py
```

Por ejemplo:

### Importación

```text
API → datos crudos → datos normalizados → PostgreSQL
```

### Procesamiento científico

```text
PostgreSQL → curvas sin procesar → cálculos → PostgreSQL
```

### Clasificación

```text
PostgreSQL → características → modelo de clasificación → PostgreSQL
```

No todos los procesos tienen que ser estrictamente ETL desde una API.

## Guardar también los datos crudos

Para un proyecto científico, puede ser útil conservar el dato original antes de transformarlo.

Una posible estructura en la base de datos sería:

```text
ingestion_runs
raw_sources
stars
light_curves
light_curve_points
calculated_features
classifications
```

Y el proceso:

```text
API
 ↓
raw_sources
 ↓
transformación
 ↓
light_curves
 ↓
análisis
 ↓
calculated_features
 ↓
clasificación
 ↓
classifications
```

Esto proporciona trazabilidad y permite reprocesar datos si cambian los algoritmos.

## Versión inicial simplificada

No hace falta implementar toda la estructura desde el primer día. Para empezar, usaría:

```text
src/data_processor/
├── main.py
├── config.py
│
├── extractors/
│   ├── api_extractor.py
│   └── xml_extractor.py
│
├── transformers/
│   └── light_curve_transformer.py
│
├── validators/
│   └── light_curve_validator.py
│
├── pipelines/
│   └── light_curve_pipeline.py
│
├── services/
│   └── curve_analysis_service.py
│
└── database/
    ├── session.py
    ├── models.py
    └── repositories.py
```

Después, cuando crezca, puedes dividir `models.py` y `repositories.py` en varios archivos.

## Punto de entrada

`main.py` debería ser pequeño:

```python
from data_processor.pipelines.import_light_curves_pipeline import (
    ImportLightCurvesPipeline,
)


def main() -> None:
    pipeline = ImportLightCurvesPipeline.build()
    pipeline.run()


if __name__ == "__main__":
    main()
```

Otra opción es exponer comandos:

```bash
python -m data_processor import-light-curves
python -m data_processor classify-pending
python -m data_processor reprocess --star-id 123
```

Para ello puedes usar `Typer`, aunque también podrías comenzar con `argparse`.

## Configuración

En `config.py` cargaría variables como:

```env
DATABASE_URL=postgresql+psycopg://user:password@postgres:5432/stars
SOURCE_API_URL=https://example.com/api
SOURCE_API_KEY=...
LOG_LEVEL=INFO
BATCH_SIZE=500
```

Usaría `pydantic-settings`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    source_api_url: str
    source_api_key: str | None = None
    batch_size: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
```

## Dependencias razonables

Para este tipo de proyecto:

```text
SQLAlchemy         ORM y acceso a PostgreSQL
Alembic            migraciones
psycopg            driver PostgreSQL
Pydantic           validación de estructuras
pydantic-settings  configuración
httpx              cliente HTTP
pandas             transformaciones tabulares
numpy              cálculos numéricos
scipy              análisis científico
astropy            astronomía, FITS, coordenadas y tiempos
Typer              interfaz CLI
pytest             tests
```

## Recomendación final

La estructura central que mantendría es:

```text
extractors/
transformers/
validators/
services/
loaders/
pipelines/
database/
domain/
```

Y la regla más importante sería:

```text
Los extractores no guardan.
Los transformers no consultan la base de datos.
Los repositorios no hacen cálculos científicos.
Los servicios no conocen el formato de la API.
Los pipelines coordinan, pero no implementan toda la lógica.
```

Eso te permitirá cambiar la API, PostgreSQL, el algoritmo de clasificación o el formato de entrada sin tener que modificar todo el proyecto.
