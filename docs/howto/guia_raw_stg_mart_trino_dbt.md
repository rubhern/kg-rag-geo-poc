# Guía paso a paso para generar y ver las 3 capas RAW → STG → MART

## Antes de empezar: cómo entrar a Trino

Para ejecutar consultas SQL en Trino desde tu contenedor, usa este comando:

```bash
docker exec -it poc-trino trino
```

Ese comando abre el cliente CLI de **Trino** dentro del contenedor `poc-trino`, para que puedas lanzar las queries SQL de esta guía.

---

# Mapa mental antes de empezar

## Tecnologías que intervienen

### MinIO
Es tu “S3 local”. Guarda los **ficheros físicos**: el CSV raw y luego los Parquet curados.

### Hive Metastore (HMS)
Es el **catálogo**. Guarda metadatos: schemas, tablas, vistas, columnas y **locations**. En tu caso esos metadatos se persisten en **`hms-db`**. Trino usa ese catálogo para saber qué existe y dónde están los ficheros.

### Trino
Es el motor SQL. No guarda los datos “dentro”. Cuando consultas una tabla del catálogo `hive`, Trino va al metastore, resuelve la ubicación, y lee o escribe en MinIO.

### dbt
Es la capa de transformación. Tus ficheros SQL no se ejecutan solos: dbt los convierte en `VIEW` o `TABLE`, respetando dependencias (`source`, `ref`) y materializaciones. `profiles.yml` define conexión por defecto a Trino y `dbt_project.yml` controla dónde se materializa cada carpeta o modelo.

---

# Paso 0. Comprobar que todo lo importante está vivo

## Qué haces
Verifica que realmente están arriba MinIO, HMS, hms-db y Trino.

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## Qué buscas
Que veas algo equivalente a:

- `minio`
- `hive-metastore`
- `hms-db`
- `poc-trino` o `trino`

## Por qué
Porque a partir de aquí:

- Trino necesita hablar con HMS
- HMS necesita hablar con `hms-db`
- Trino y HMS necesitan ver MinIO

---

# Paso 1. Crear los 3 schemas del catálogo Hive

Esto se hace **en Trino**.

## Query

```sql
CREATE SCHEMA IF NOT EXISTS hive.raw_s3
WITH (location='s3a://raw/hive/raw_s3/');

CREATE SCHEMA IF NOT EXISTS hive.stg_s3
WITH (location='s3a://curated/hive/stg/');

CREATE SCHEMA IF NOT EXISTS hive.curated_s3
WITH (location='s3a://curated/hive/curated/');
```

## Qué hace esta query
Le estás diciendo a **Trino**, usando el catálogo `hive`:

- crea el schema lógico `raw_s3`
- crea el schema lógico `stg_s3`
- crea el schema lógico `curated_s3`

y para cada uno deja registrada una **ruta base** (`location`) donde vivirán las tablas “gestionadas”.

## Qué tecnología actúa aquí
1. Tú lanzas SQL en **Trino**
2. Trino llama al **Hive Metastore**
3. El metastore guarda ese schema y su location en **`hms-db`**

## Muy importante
Esto **no suele crear todavía ficheros visibles** en MinIO.  
Lo que crea de verdad es **metadato en el catálogo**. En MinIO solo aparecerán objetos cuando una tabla materializada escriba datos.

## Cómo validarlo

```sql
SHOW SCHEMAS FROM hive;
```

### Para qué sirve
Te lista los schemas registrados en el catálogo `hive`.

### Qué deberías ver
Al menos:

- `raw_s3`
- `stg_s3`
- `curated_s3`

---

# Paso 2. Registrar la capa RAW como tabla externa

Tu fichero ya existe físicamente en MinIO en esta ruta:

```text
raw/source=file/dt=2026-01-30/cc2e2ea2ff4a77192df93c41af8a078767557e3b2573b5140471684a1d5ed743/traffic.csv
```

Ahora hay que **decirle a Trino que eso es una tabla**.

## Query

Primero:

```sql
DROP TABLE IF EXISTS hive.raw_s3.traffic_csv;
```

Luego:

```sql
CREATE TABLE hive.raw_s3.traffic_csv (
  reading_id        varchar,
  sensor_id         varchar,
  road              varchar,
  direction         varchar,
  road_segment_id   varchar,
  city              varchar,
  lat               varchar,
  lon               varchar,
  measured_at_utc   varchar,
  vehicle_count     varchar,
  avg_speed_kmh     varchar,
  occupancy_pct     varchar,
  congestion_level  varchar,
  incident_flag     varchar,
  source_system     varchar
)
WITH (
  format = 'CSV',
  external_location = 's3://raw/source=file/dt=2026-01-30/cc2e2ea2ff4a77192df93c41af8a078767557e3b2573b5140471684a1d5ed743/',
  skip_header_line_count = 1
);
```

## Qué hace esta query
Registra una **tabla externa** en el catálogo.

Eso significa:

- los datos **ya existen** en MinIO
- Trino **no los copia**
- Trino simplemente registra que en esa carpeta hay un dataset CSV con esas columnas

## Por qué todas las columnas van como `varchar`
Porque **RAW no limpia ni tipa nada**.  
La regla sana aquí es: “entra como venga”. Ya haremos casts y normalización en STG.

## Validaciones

### 2.1 Ver estructura
```sql
DESCRIBE hive.raw_s3.traffic_csv;
```

**Para qué sirve**  
Te enseña columnas y tipos registrados.

### 2.2 Ver que lee filas
```sql
SELECT *
FROM hive.raw_s3.traffic_csv
LIMIT 10;
```

**Para qué sirve**  
Primera validación funcional: Trino ya está leyendo el CSV desde MinIO.

### 2.3 Contar filas
```sql
SELECT count(*)
FROM hive.raw_s3.traffic_csv;
```

**Para qué sirve**  
Saber si está leyendo el dataset completo.

### 2.4 Ver desde qué fichero lee
```sql
SELECT "$path"
FROM hive.raw_s3.traffic_csv
LIMIT 5;
```

**Para qué sirve**  
Te muestra la ruta real del fichero físico que está escaneando Trino.

---

# Paso 3. Revisar tu proyecto dbt antes de ejecutarlo

## `profiles.yml`
```yaml
poc_trino:
  target: dev
  outputs:
    dev:
      type: trino
      method: none
      user: dbt
      host: trino
      port: 8080
      database: hive
      schema: raw_s3
      threads: 4
```

### Qué significa
- `type: trino`: dbt se conectará a Trino
- `database: hive`: el catálogo por defecto será `hive`
- `schema: raw_s3`: schema por defecto si no se sobreescribe
- `host: trino`: el hostname dentro de la red Docker

---

## `dbt_project.yml`
```yaml
models:
  poc_trino:
    stg:
      +schema: stg_s3
      +materialized: view
    marts:
      +schema: curated_s3
      +materialized: table
      +on_table_exists: drop
      +properties:
        format: "'PARQUET'"
```

### Qué significa
- todo lo que cuelgue de `models/stg` se materializa en `stg_s3` como **view**
- todo lo que cuelgue de `models/marts` se materializa en `curated_s3` como **table**
- si la tabla MART ya existe, dbt la rehace con `drop`
- el formato de salida será **PARQUET**

---

## `sources.yml`
Declara que `traffic_csv` es una **fuente RAW**, no un modelo creado por dbt.

---

## `stg_traffic.sql`
Tu STG:

- lee desde `source('raw_s3', 'traffic_csv')`
- hace casts
- parsea `measured_at_utc`
- extrae `ingest_dt` usando `"$path"`
- normaliza `congestion_level`
- deja `incident_flag` como texto normalizado

---

## `fct_traffic_daily.sql`
Tu MART:

- agrupa por fecha, sensor y ciudad
- calcula métricas agregadas
- se materializa como **table PARQUET**

### Ojo aquí
Con el fichero actual:

```sql
max(congestion_level) as congestion_level_max
```

eso hace un máximo **lexicográfico**, no de severidad.  
Para **ver la capa MART** te vale.  
Para que sea “máximo de negocio”, luego te recomendaré cambiarlo a `max_by(...)`.

---

# Paso 4. Revisar si tienes el macro que evita schemas raros

Tu `dbt_project.yml` tiene:

```yaml
macro-paths: ["macros"]
```

Revisa si existe:

```bash
cd dbt/analytics/poc_trino
ls -R
```

## Qué buscar
Un fichero así:

```text
macros/generate_schema_name.sql
```

## Si no existe, créalo

```bash
mkdir -p macros
cat > macros/generate_schema_name.sql <<'EOF'
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
EOF
```

## Para qué sirve
Evita que dbt te invente schemas como:

```text
raw_s3_stg_s3
raw_s3_curated_s3
```

Ese fue el origen del error con `file:/opt/hive/data/warehouse/...`.  
Con este macro, dbt usa **exactamente** `stg_s3` y `curated_s3`.

---

# Paso 5. Probar conexión dbt → Trino

Desde la carpeta del proyecto dbt:

```bash
cd dbt/analytics/poc_trino
```

## Si tienes servicio `dbt` en docker compose
```bash
docker compose run --rm dbt debug
```

## Si ya estás dentro de un contenedor o shell dbt
```bash
dbt debug
```

## Qué hace
- carga `profiles.yml`
- carga `dbt_project.yml`
- intenta conectar a Trino

## Qué deberías ver
- conexión OK
- perfil OK
- proyecto OK

## Por qué este paso es importante
Porque si aquí falla, todavía no hemos tocado datos. Es el punto barato para corregir red, hostname, auth o paths.

---

# Paso 6. Generar la capa STG

## Comando

```bash
cd dbt/analytics/poc_trino
docker compose run --rm dbt run -s stg_traffic
```

o, si ya estás dentro del entorno dbt:

```bash
dbt run -s stg_traffic
```

## Qué hace dbt aquí
Toma `models/stg/stg_traffic.sql` y lo materializa como:

```text
hive.stg_s3.stg_traffic
```

y como en `dbt_project.yml` STG es `view`, lo que crea realmente es una **vista**.

## Qué significa una vista aquí
No crea ficheros en MinIO.  
Guarda una **definición SQL** en el metastore. Luego, cuando consultas la vista, Trino expande ese SQL y lee desde RAW.

## Validaciones

### 6.1 Ver que la vista existe
```sql
SHOW TABLES FROM hive.stg_s3;
```

### 6.2 Ver la definición de la vista
```sql
SHOW CREATE VIEW hive.stg_s3.stg_traffic;
```

**Para qué sirve**  
Te enseña el SQL lógico almacenado.

### 6.3 Consultar datos limpios
```sql
SELECT *
FROM hive.stg_s3.stg_traffic
LIMIT 10;
```

**Para qué sirve**  
Validar que:
- las columnas numéricas salen tipadas
- `measured_at_ts` tiene valor
- `ingest_dt` se extrae bien desde `$path`

### 6.4 Comprobar parseo de timestamp
```sql
SELECT
  count(*) as total_rows,
  count_if(measured_at_ts is null) as null_timestamps
FROM hive.stg_s3.stg_traffic;
```

**Para qué sirve**  
Medir si tu parseo temporal funciona.

### 6.5 Comprobar normalización de congestión
```sql
SELECT
  congestion_level,
  congestion_level_rank,
  count(*) as rows
FROM hive.stg_s3.stg_traffic
GROUP BY 1,2
ORDER BY 1,2;
```

**Para qué sirve**  
Ver si `LOW` y `MEDIUM` están cayendo en los ranks correctos.

---

# Paso 7. Generar la capa MART

## Comando

```bash
cd dbt/analytics/poc_trino
docker compose run --rm dbt run -s fct_traffic_daily
```

o:

```bash
dbt run -s fct_traffic_daily
```

## Qué hace dbt aquí
Materializa el modelo como tabla:

```text
hive.curated_s3.fct_traffic_daily
```

y como le has puesto:

```yaml
+materialized: table
+properties:
  format: "'PARQUET'"
```

Trino crea una **tabla física** cuyos datos quedan escritos como **Parquet** en la ruta del schema `curated_s3`.

## Qué tecnología actúa
1. dbt lanza SQL a Trino
2. Trino lee la vista STG
3. Trino escribe **Parquet** en MinIO
4. Trino registra la tabla final en Hive Metastore

## Validaciones

### 7.1 Ver que la tabla existe
```sql
SHOW TABLES FROM hive.curated_s3;
```

### 7.2 Ver estructura y propiedades
```sql
SHOW CREATE TABLE hive.curated_s3.fct_traffic_daily;
```

**Para qué sirve**  
Confirmar que es una tabla materializada en `curated_s3`.

### 7.3 Consultar el resultado
```sql
SELECT *
FROM hive.curated_s3.fct_traffic_daily
ORDER BY traffic_date DESC
LIMIT 20;
```

**Para qué sirve**  
Ya estás viendo la capa MART.

### 7.4 Ver los ficheros físicos que está leyendo
```sql
SELECT "$path"
FROM hive.curated_s3.fct_traffic_daily
LIMIT 10;
```

**Para qué sirve**  
Demostrar que, aunque consultas una “tabla de Trino”, lo que realmente está leyendo son **ficheros Parquet** del bucket `curated`.

---

# Paso 8. Ejecutar tests dbt

Tu `schema.yml` ahora mismo define dos tests `not_null` en MART.

## Comando

```bash
cd dbt/analytics/poc_trino
docker compose run --rm dbt test
```

## Qué hace
Ejecuta tests automáticos sobre los modelos definidos.

## Qué valida ahora mismo
- `traffic_date` no debe ser null
- `sensor_id` no debe ser null

---

# Paso 9. Qué estás viendo exactamente en cada capa

## RAW
Tabla externa:

```text
hive.raw_s3.traffic_csv
```

- datos tal cual llegan
- todos los campos como texto
- no reescribe nada
- apunta a CSV ya existente en MinIO

## STG
Vista:

```text
hive.stg_s3.stg_traffic
```

- limpia y tipa
- parsea fechas
- normaliza campos
- no crea ficheros

## MART
Tabla materializada:

```text
hive.curated_s3.fct_traffic_daily
```

- agrega
- produce un dataset final
- sí crea ficheros **Parquet** en MinIO

---

# Paso 10. Pequeño ajuste recomendado antes de darlo por redondo

Con tus ficheros actuales, yo haría este ajuste en `fct_traffic_daily.sql`:

cambia:

```sql
max(congestion_level) as congestion_level_max,
```

por:

```sql
max_by(congestion_level, congestion_level_rank) as congestion_level_max,
```

## Por qué
`max(congestion_level)` en strings compara alfabéticamente.  
No significa “severidad más alta”.

Si haces ese cambio, luego vuelves a ejecutar:

```bash
docker compose run --rm dbt run -s fct_traffic_daily
```

---

# Resumen operativo: el camino completo

## En Trino
1. Crear schemas
2. Crear tabla RAW externa
3. Validar RAW

## En dbt
4. Revisar macro
5. `dbt debug`
6. `dbt run -s stg_traffic`
7. Validar STG
8. `dbt run -s fct_traffic_daily`
9. Validar MART
10. `dbt test`

---

# Orden exacto de comandos

## En Trino
```sql
CREATE SCHEMA IF NOT EXISTS hive.raw_s3
WITH (location='s3a://raw/hive/raw_s3/');

CREATE SCHEMA IF NOT EXISTS hive.stg_s3
WITH (location='s3a://curated/hive/stg/');

CREATE SCHEMA IF NOT EXISTS hive.curated_s3
WITH (location='s3a://curated/hive/curated/');

DROP TABLE IF EXISTS hive.raw_s3.traffic_csv;

CREATE TABLE hive.raw_s3.traffic_csv (
  reading_id        varchar,
  sensor_id         varchar,
  road              varchar,
  direction         varchar,
  road_segment_id   varchar,
  city              varchar,
  lat               varchar,
  lon               varchar,
  measured_at_utc   varchar,
  vehicle_count     varchar,
  avg_speed_kmh     varchar,
  occupancy_pct     varchar,
  congestion_level  varchar,
  incident_flag     varchar,
  source_system     varchar
)
WITH (
  format = 'CSV',
  external_location = 's3://raw/source=file/dt=2026-01-30/cc2e2ea2ff4a77192df93c41af8a078767557e3b2573b5140471684a1d5ed743/',
  skip_header_line_count = 1
);

SELECT count(*) FROM hive.raw_s3.traffic_csv;
SELECT "$path" FROM hive.raw_s3.traffic_csv LIMIT 5;
```

## En la carpeta dbt
```bash
cd dbt/analytics/poc_trino
ls -R
```

Si falta el macro:
```bash
mkdir -p macros
cat > macros/generate_schema_name.sql <<'EOF'
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
EOF
```

Luego:
```bash
docker compose run --rm dbt debug
docker compose run --rm dbt run -s stg_traffic
docker compose run --rm dbt run -s fct_traffic_daily
docker compose run --rm dbt test
```

## Validaciones en Trino
```sql
SELECT * FROM hive.stg_s3.stg_traffic LIMIT 10;
SELECT * FROM hive.curated_s3.fct_traffic_daily LIMIT 20;
SELECT "$path" FROM hive.curated_s3.fct_traffic_daily LIMIT 10;
```

---

# Primer bloque que te recomendaría ejecutar

## En Trino
```sql
CREATE SCHEMA IF NOT EXISTS hive.raw_s3
WITH (location='s3a://raw/hive/raw_s3/');

CREATE SCHEMA IF NOT EXISTS hive.stg_s3
WITH (location='s3a://curated/hive/stg/');

CREATE SCHEMA IF NOT EXISTS hive.curated_s3
WITH (location='s3a://curated/hive/curated/');

DROP TABLE IF EXISTS hive.raw_s3.traffic_csv;

CREATE TABLE hive.raw_s3.traffic_csv (
  reading_id        varchar,
  sensor_id         varchar,
  road              varchar,
  direction         varchar,
  road_segment_id   varchar,
  city              varchar,
  lat               varchar,
  lon               varchar,
  measured_at_utc   varchar,
  vehicle_count     varchar,
  avg_speed_kmh     varchar,
  occupancy_pct     varchar,
  congestion_level  varchar,
  incident_flag     varchar,
  source_system     varchar
)
WITH (
  format = 'CSV',
  external_location = 's3://raw/source=file/dt=2026-01-30/cc2e2ea2ff4a77192df93c41af8a078767557e3b2573b5140471684a1d5ed743/',
  skip_header_line_count = 1
);

SELECT count(*) FROM hive.raw_s3.traffic_csv;
SELECT "$path" FROM hive.raw_s3.traffic_csv LIMIT 5;
```

Cuando eso funcione, ya saltas a dbt y generas STG y MART.
