# Carga de datos en PostGIS

## 1. Alcance de este documento

Este documento resume **lo trabajado hasta ahora para el Día 7 de la POC**, centrado en la preparación y carga de datos geográficos en **PostgreSQL + PostGIS**.

El foco de este tramo ha sido:

- preparar la fuente geográfica de regiones,
- generar `regions.geojson`,
- cargar regiones en PostGIS,
- validar la tabla espacial cargada,
- y dejar listo el siguiente tramo: **carga de sensores + joins espaciales + queries GIS**.

No cubre todavía dashboards, agente, grafo ni observabilidad avanzada.

---

## 2. Objetivo funcional de esta parte del Día 7

El objetivo del Día 7 es cerrar la parte GIS mínima de la POC para el caso de uso de **tráfico urbano por sensor**:

- regiones geográficas sintéticas,
- sensores con localización sintética,
- carga en PostGIS,
- validación de joins espaciales,
- preparación de queries GIS reutilizables.

La meta intermedia ya alcanzada es disponer de una tabla espacial de regiones cargada y validada en PostGIS, lista para cruzarse con sensores.

---

## 3. Modelo conceptual acordado

Durante el trabajo se fijó este modelo mental para no mezclar dimensiones, hechos y agregados:

- **`traffic.csv`** = hechos observados de tráfico
- **`sensor_locations.csv`** = catálogo de sensores y su localización
- **`regions.csv`** = catálogo geográfico base de regiones
- **`mart_traffic_sensor_geo`** = dataset analítico enriquecido
- **`mart_region_daily_kpis`** = dataset agregado para dashboard

La decisión importante fue tratar `regions` como **master data geográfico** y no como un agregado funcional derivado de una MART.

---

## 4. Datos de partida utilizados

En esta parte del trabajo se han manejado estas piezas:

### 4.1 Fuente de tráfico

- Fichero de tráfico diario en CSV/Parquet
- Datos agregados por sensor y fecha

### 4.2 Fuente de regiones

- `poc_regions_source.csv`
- Fichero sintético/inventado para la POC
- Incluye `region_id`, `region_name`, `city`, `region_type`, `srid`, `geom_wkt`, `source`

### 4.3 Fuente de sensores

- `poc_sensor_locations_source.csv`
- Fichero sintético con localización de sensores

### 4.4 Modelos dbt ya disponibles

- `stg_regions`
- `dim_regions`
- `stg_sensor_locations`

---

## 5. Flujo por capas trabajado

Se ha trabajado este flujo para la parte de regiones:

```text
RAW regions.csv
-> stg_regions
-> dim_regions
-> export CSV
-> regions.geojson
-> PostGIS (serving.regions)
```

### 5.1 RAW

Se acordó tratar la fuente de regiones como un dataset independiente en RAW, por ejemplo con una ruta conceptual como esta:

```text
raw/source=file/entity=regions/dt=2026-01-20/run=001/poc_regions_source.csv
```

### 5.2 STG

Se trabajó con `stg_regions` para limpieza y tipado de la fuente.

### 5.3 DIM

Se concluyó que el “mart” de regiones debía modelarse como una **dimensión geográfica canónica**, es decir, `dim_regions`.

### 5.4 Export GIS

A partir de `dim_regions` se decidió generar:

1. un CSV exportado desde Trino,
2. y después un `regions.geojson` mediante un script Python.

### 5.5 Serving GIS

Una vez generado el GeoJSON, se decidió cargarlo directamente en PostGIS con `ogr2ogr`, dentro del esquema **`serving`**.

---

## 6. Creación de `stg_regions`

La capa `stg_regions` se planteó como limpieza y tipado de la fuente RAW.

SQL utilizado como referencia:

```sql
select
    trim(region_id) as region_id,
    trim(region_name) as region_name,
    trim(region_type) as region_type,
    trim(city) as city,
    cast(srid as integer) as srid,
    trim(geom_wkt) as geom_wkt,
    trim(source) as source
from raw_regions
```

### Objetivo de `stg_regions`

- limpiar espacios,
- tipar `srid`,
- dejar preparado el `geom_wkt`,
- y garantizar un contrato consistente para la dimensión.

---

## 7. Comprobaciones previas sobre `stg_regions`

Antes de construir `dim_regions`, se propusieron dos comprobaciones para validar duplicados y conflictos geométricos.

### 7.1 Duplicados por región

```sql
select
    region_id,
    count(*) as row_count
from {{ ref('stg_regions') }}
group by region_id
having count(*) > 1
order by row_count desc
```

### 7.2 Conflictos geométricos por región

```sql
select
    region_id,
    count(distinct geom_wkt) as distinct_geometries
from {{ ref('stg_regions') }}
group by region_id
having count(distinct geom_wkt) > 1
order by distinct_geometries desc
```

### Qué se pretendía validar

- que cada `region_id` represente una única región,
- que una región no tenga geometrías contradictorias,
- y que `dim_regions` pueda crearse con un grain estable de una fila por región.

---

## 8. Creación de `dim_regions`

Se decidió crear `dim_regions` como la **dimensión geográfica canónica**.

### Regla funcional fijada

**1 fila = 1 región**

### Campos esperados

- `region_id`
- `region_name`
- `city`
- `region_type`
- `srid`
- `geom_wkt`
- `source`

### SQL propuesto para `dim_regions.sql`

```sql
{{ config(materialized='table') }}

select distinct
    trim(region_id) as region_id,
    trim(region_name) as region_name,
    trim(city) as city,
    trim(region_type) as region_type,
    cast(srid as integer) as srid,
    trim(geom_wkt) as geom_wkt,
    trim(source) as source
from {{ ref('stg_regions') }}
where region_id is not null
  and region_name is not null
  and geom_wkt is not null
  and cast(srid as integer) = 4326
```

### Ejecución del modelo

```bash
dbt run --select dim_regions
```

O bien:

```bash
dbt run --select stg_regions dim_regions
```

### Validaciones posteriores propuestas

```sql
select count(*) from {{ ref('dim_regions') }};
```

```sql
select
    region_id,
    count(*) as row_count
from {{ ref('dim_regions') }}
group by region_id
having count(*) > 1
```

```sql
select distinct srid
from {{ ref('dim_regions') }}
```

---

## 9. Exportación de `dim_regions` a CSV desde Trino

Una vez construida `dim_regions`, se decidió exportarla a un CSV intermedio para después generar el GeoJSON.

### Comando correcto de exportación

```bash
docker exec -i poc-trino trino \
  --execute "
    select
        region_id,
        region_name,
        city,
        region_type,
        srid,
        geom_wkt,
        source
    from hive.default.dim_regions
    order by region_id
  " \
  --output-format CSV_HEADER \
  > regions_export.csv
```

### Motivo de usar `CSV_HEADER`

Inicialmente se sugirió un formato sin quoting, pero se detectó que eso rompe el campo `geom_wkt` porque el WKT contiene comas internas.

Por tanto, el formato correcto acordado fue:

```bash
--output-format CSV_HEADER
```

Esto mantiene las comillas necesarias para que el CSV siga siendo parseable.

---

## 10. Script Python para generar `regions.geojson`

Se trabajó con un script Python llamado:

```text
infra/scripts/export_regions_geojson.py
```

### Responsabilidad del script

- leer `regions_export.csv`,
- tomar el campo `geom_wkt`,
- convertirlo a geometría real,
- construir un `FeatureCollection` GeoJSON,
- y generar el fichero `regions.geojson`.

### Dependencia utilizada

```bash
python -m pip install --upgrade pip
python -m pip install shapely
```

### Comando para ejecutar el script

```bash
python infra/scripts/export_regions_geojson.py
```

### Problemas encontrados y resueltos

#### 10.1 Dependencia faltante

```text
ModuleNotFoundError: No module named 'shapely'
```

Se resolvió instalando `shapely` en el mismo intérprete Python que ejecutaba el script.

#### 10.2 Parseo WKT roto

```text
shapely.errors.GEOSException: ParseException: Expected word but encountered end of stream
```

La causa real estaba en el CSV exportado: `geom_wkt` se había roto por usar un formato de exportación incorrecto. La solución fue regenerar el CSV con `CSV_HEADER`.

---

## 11. Validaciones sobre el CSV y el GeoJSON

Se propusieron varias comprobaciones rápidas para validar la exportación.

### Ver primeras líneas del CSV

```bash
head -2 regions_export.csv
```

### Ejecutar el script de exportación

```bash
python infra/scripts/export_regions_geojson.py
```

### Ver primeras líneas del GeoJSON

```bash
head -20 regions.geojson
```

### Contar features generadas

```bash
python -c "import json; print(len(json.load(open('regions.geojson', encoding='utf-8'))['features']))"
```

El resultado esperado con las regiones sintéticas era **5 features**.

---

## 12. Carga de `regions.geojson` en PostGIS

Una vez generado `regions.geojson`, se decidió cargarlo en PostGIS usando `ogr2ogr` ejecutado dentro de un contenedor Docker.

### 12.1 Por qué usar `ogr2ogr`

`ogr2ogr` es una utilidad de **GDAL/OGR** para convertir y mover datos vectoriales geoespaciales entre formatos, por ejemplo:

- GeoJSON
- Shapefile
- GeoPackage
- PostGIS

En este caso se usa para:

- leer `regions.geojson`,
- interpretar atributos y geometría,
- crear la tabla de salida en PostgreSQL/PostGIS,
- y cargar la geometría en una columna espacial real.

### 12.2 Estrategia elegida

En vez de instalar GDAL en Windows, se optó por usar una imagen Docker de GDAL y ejecutar `ogr2ogr` como contenedor efímero.

Esto evita problemas típicos de instalación local y hace el proceso reproducible.

### 12.3 Problema encontrado con la imagen inicial

Primero se intentó usar una imagen antigua basada en Docker Hub y falló con error de `manifest unknown`.

La corrección fue usar la imagen publicada en GitHub Container Registry:

```text
ghcr.io/osgeo/gdal:alpine-normal-3.12.3
```

### 12.4 Problema de conectividad inicial

Al probar la conexión desde el contenedor de GDAL, se detectó que **`localhost` no era correcto** como host de PostgreSQL.

Motivo:

- `localhost` dentro del contenedor apunta al propio contenedor de GDAL,
- no al contenedor `postgres`,
- y por tanto la conexión era rechazada.

La solución correcta fue:

1. lanzar el contenedor de GDAL en la misma red Docker Compose,
2. conectar a PostgreSQL usando el host `postgres`,
3. y autenticarse con usuario y password reales.

### 12.5 Validación de conectividad con `psql`

Antes de lanzar `ogr2ogr`, se validó que el contenedor temporal podía llegar a la base:

```bash
docker run --rm \
  --network infra_default \
  -e PGPASSWORD=pocpass \
  postgres:16-alpine \
  psql -h postgres -U poc -d poc -c "select 1;"
```

Esta prueba funcionó correctamente y confirmó:

- red Docker OK,
- resolución DNS interna OK,
- credenciales OK.

### 12.6 Comando final utilizado para la carga

En Git Bash / WSL, usando la misma red Docker Compose:

```bash
docker run --rm \
  --network infra_default \
  -v "$(pwd):/work" \
  ghcr.io/osgeo/gdal:alpine-normal-3.12.3 \
  ogr2ogr \
    -progress \
    -f PostgreSQL \
    "PG:host=postgres port=5432 dbname=poc user=poc password=pocpass active_schema=serving" \
    /work/regions.geojson \
    -nln regions \
    -lco GEOMETRY_NAME=geom \
    -nlt PROMOTE_TO_MULTI \
    -overwrite
```

### 12.7 Qué hace cada parte del comando

- `docker run --rm`  
  Lanza un contenedor temporal y lo elimina al terminar.

- `--network infra_default`  
  Mete el contenedor en la misma red que usa el stack Docker Compose.

- `-v "$(pwd):/work"`  
  Monta el directorio actual para que el contenedor vea `regions.geojson`.

- `ghcr.io/osgeo/gdal:alpine-normal-3.12.3`  
  Imagen que contiene `ogr2ogr`.

- `ogr2ogr`  
  Herramienta de conversión/carga GIS.

- `-f PostgreSQL`  
  Formato de salida: PostgreSQL/PostGIS.

- `"PG:host=postgres ... active_schema=serving"`  
  Cadena de conexión a PostgreSQL dentro de la red Docker.

- `/work/regions.geojson`  
  Fichero de entrada.

- `-nln regions`  
  Nombre de la tabla de salida: `regions`.

- `-lco GEOMETRY_NAME=geom`  
  Nombre de la columna geométrica.

- `-nlt PROMOTE_TO_MULTI`  
  Homogeneiza la geometría a multi-geometría cuando aplica.

- `-overwrite`  
  Reemplaza la tabla si ya existía.

---

## 13. Validación de la tabla `serving.regions`

Una vez cargado el GeoJSON en PostGIS, se ejecutó la validación de la tabla resultante.

### 13.1 Comprobación de columnas

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'serving'
  AND table_name = 'regions'
ORDER BY ordinal_position;
```

### 13.2 Validación de contenido y geometría

```sql
SELECT
    count(*)                              AS total_rows,
    min(ST_SRID(geom))                    AS min_srid,
    max(ST_SRID(geom))                    AS max_srid,
    bool_and(ST_IsValid(geom))            AS all_valid,
    string_agg(DISTINCT ST_GeometryType(geom), ', ') AS geom_types
FROM serving.regions;
```

### 13.3 Resultado alcanzado

Las validaciones han quedado **OK**, por lo que se considera cerrada la carga de regiones a PostGIS para esta fase.

Esto implica que:

- la tabla `serving.regions` existe,
- la geometría se ha cargado correctamente,
- el SRID es consistente,
- y las geometrías son válidas.

---

## 14. Estado actual alcanzado

En este punto del Día 7 el estado es:

- `stg_regions` creado,
- `dim_regions` creado y ejecutado,
- `regions_export.csv` generado correctamente,
- `regions.geojson` generado correctamente,
- `serving.regions` cargada en PostGIS con `ogr2ogr`,
- validaciones de la tabla espacial realizadas y correctas.

Este ya es un hito relevante: la dimensión geográfica de regiones está disponible en la capa serving GIS.

---

## 15. Próximos pasos recomendados

Una vez cerrada la carga de regiones, el siguiente bloque lógico es:

### 15.1 Crear índices sobre `serving.regions`

```sql
CREATE INDEX IF NOT EXISTS idx_regions_geom
  ON serving.regions
  USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_regions_region_id
  ON serving.regions (region_id);

ANALYZE serving.regions;
```

### 15.2 Preparar el dataset de sensores para PostGIS

Partiendo de `stg_sensor_locations`, exportar un CSV intermedio desde Trino:

```bash
docker exec -i poc-trino trino --output-format CSV_HEADER --execute "
SELECT
  sensor_id,
  city,
  region_id,
  longitude,
  latitude,
  srid,
  geom_wkt,
  source
FROM hive.default.stg_sensor_locations
" > sensor_locations.csv
```

### 15.3 Crear tabla raw de sensores en Postgres

```sql
DROP TABLE IF EXISTS serving.sensor_locations_raw;

CREATE TABLE serving.sensor_locations_raw (
    sensor_id   text,
    city        text,
    region_id   text,
    longitude   double precision,
    latitude    double precision,
    srid        integer,
    geom_wkt    text,
    source      text
);
```

### 15.4 Cargar CSV de sensores en Postgres

```bash
docker cp ./sensor_locations.csv poc-postgres:/tmp/sensor_locations.csv
```

```sql
COPY serving.sensor_locations_raw
FROM '/tmp/sensor_locations.csv'
DELIMITER ','
CSV HEADER;
```

### 15.5 Construir tabla espacial final de sensores

```sql
DROP TABLE IF EXISTS serving.sensor_locations;

CREATE TABLE serving.sensor_locations AS
SELECT
    trim(sensor_id)              AS sensor_id,
    trim(city)                   AS city,
    trim(region_id)              AS expected_region_id,
    longitude,
    latitude,
    COALESCE(srid, 4326)         AS srid,
    CASE
        WHEN geom_wkt IS NOT NULL AND btrim(geom_wkt) <> ''
            THEN ST_SetSRID(ST_GeomFromText(geom_wkt), COALESCE(srid, 4326))
        ELSE
            ST_SetSRID(ST_MakePoint(longitude, latitude), COALESCE(srid, 4326))
    END::geometry(Point, 4326)   AS geom,
    trim(source)                 AS source
FROM serving.sensor_locations_raw;
```

### 15.6 Indexar sensores

```sql
CREATE INDEX IF NOT EXISTS idx_sensor_locations_geom
  ON serving.sensor_locations
  USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_sensor_locations_expected_region
  ON serving.sensor_locations (expected_region_id);

ANALYZE serving.sensor_locations;
```

### 15.7 Validar join espacial con regiones

```sql
SELECT
    s.sensor_id,
    s.city,
    s.expected_region_id,
    r.region_id   AS spatial_region_id,
    r.region_name
FROM serving.sensor_locations s
LEFT JOIN serving.regions r
  ON ST_Intersects(s.geom, r.geom)
ORDER BY s.sensor_id;
```

### 15.8 Detectar sensores sin región o con mismatch

```sql
SELECT
    s.sensor_id,
    s.expected_region_id,
    r.region_id AS spatial_region_id
FROM serving.sensor_locations s
LEFT JOIN serving.regions r
  ON ST_Intersects(s.geom, r.geom)
WHERE r.region_id IS NULL
   OR s.expected_region_id <> r.region_id
ORDER BY s.sensor_id;
```

### 15.9 Crear vista de validación reutilizable

```sql
CREATE OR REPLACE VIEW serving.v_sensor_region_validation AS
SELECT
    s.sensor_id,
    s.city,
    s.expected_region_id,
    r.region_id     AS spatial_region_id,
    r.region_name,
    CASE
        WHEN r.region_id IS NULL THEN 'NO_SPATIAL_MATCH'
        WHEN s.expected_region_id <> r.region_id THEN 'MISMATCH'
        ELSE 'OK'
    END AS validation_status
FROM serving.sensor_locations s
LEFT JOIN serving.regions r
  ON ST_Intersects(s.geom, r.geom);
```

---

## 16. Resumen ejecutivo

En esta parte del Día 7 se ha cerrado con éxito la preparación y carga de la dimensión geográfica de regiones en PostGIS.

El flujo trabajado ha sido:

```text
RAW -> STG -> DIM -> CSV -> GeoJSON -> PostGIS
```

y los principales problemas prácticos resueltos han sido:

- modelado correcto de `regions` como master data geográfico,
- creación de `dim_regions`,
- exportación CSV con quoting correcto para WKT,
- generación de `regions.geojson`,
- uso de `ogr2ogr` en Docker en vez de instalación local,
- corrección del problema de red entre contenedores,
- y validación final de `serving.regions`.

Con esto queda preparada la base para el siguiente tramo del Día 7:

**cargar sensores, validar `ST_Intersects` y dejar las queries GIS listas.**
