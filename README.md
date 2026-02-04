# POC – Data Platform (Ingestion → RAW → Curated → Query/Agent)

This repository contains a **local, docker-compose-based** Proof of Concept to validate an end-to-end flow:
data ingestion from multiple sources, RAW storage, curation, analytics/dashboards, and a conversational/agent layer.

---

## What’s inside (high level)

- **Ingestors**: pull/receive data from sources (file / HTTP / stream).
- **RAW storage**: object storage (e.g., S3-compatible) for immutable raw dumps.
- **Curated storage**: Parquet datasets in MinIO (CURATED zone) and/or PostgreSQL + PostGIS for serving/query workloads.
- **Streaming (optional)**: Kafka/Redpanda for event-driven ingestion and decoupling.
- **Observability**: metrics/logs/traces (OpenTelemetry stack) + Grafana dashboards.
- **Agent/API (optional)**: a thin backend to search curated data and/or support RAG.

---

## Quickstart

### Prerequisites
- Docker Engine + Docker Compose plugin
- (Optional) GNU Make or a shell compatible with the scripts

### 1) Configure environment
Copy the example environment file and adjust if needed:

```bash
cp .env.example .env
```

### 2) Start the platform
```bash
docker compose up -d
```

### 3) Check status
```bash
docker compose ps
```

You should see all services in `running` state and (where configured) `healthy`.

### 4) Stop the platform
```bash
docker compose down
```

### 5) Full reset (⚠️ destroys volumes)
```bash
docker compose down -v
```

---

## Repository layout (recommended)

```text
.
├── docker-compose.yml
├── .env.example
├── contracts/
│   ├── conventions.md
│   ├── events/
│   └── examples/
├── infra/
│   ├── postgres/
│   │   └── initdb/
│   ├── object-storage/
│   │   └── init/
│   ├── kafka/
│   │   └── init/
│   └── grafana/
│       └── provisioning/
├── services/
│   ├── ingestor-file/
│   ├── ingestor-http/
│   ├── ingestor-stream/
│   └── agent-api/
└── scripts/
    ├── up.sh
    ├── down.sh
    ├── reset.sh
    └── smoke.sh
```

> If your current tree differs, keep the idea: **infra is platform**, **services is code**, **contracts is truth**.

---


## Endpoints (default local ports)

Ports are defined in `.env` and referenced from `docker-compose.yml`.

| Component | URL | Notes |
|---|---|---|
| Kafka UI | http://localhost:8080 | Browse topics/messages |
| MinIO API | http://localhost:${MINIO_PORT} | S3-compatible endpoint (health: `/minio/health/live`) |
| MinIO Console | http://localhost:${MINIO_CONSOLE_PORT} | Buckets/objects UI |
| PostgreSQL | localhost:${PG_PORT} | `poc` database (PostGIS + pgvector optional) |
| Grafana | http://localhost:${GRAFANA_PORT} | Dashboards (if enabled) |
| Prometheus | http://localhost:${PROMETHEUS_PORT} | Metrics |
| Loki | http://localhost:${LOKI_PORT} | Logs |
| Tempo | http://localhost:${TEMPO_HTTP_PORT} | Traces |
| Mock API (WireMock) | http://localhost:8089 | Deterministic HTTP source for Day 4 |

---

## Smoke checks

From the infra folder (where `docker-compose.yml` and `.env` live):

```bash
chmod +x smoke_day*.sh
./smoke_day1.sh
./smoke_day2.sh
./smoke_day3.sh
./smoke_day4.sh
./smoke_day5.sh
```

- Day 3 uses `ingestor-file` under the `manual` profile.
- Day 4 uses `mock-api` (WireMock) + `ingestor-http` under the `manual` profile.
- Day 5 uses `ingestor-stream-consumer` (always-on) + `ingestor-stream-producer` (manual profile) to validate streaming ingestion.

---

## Definition of Done

### Day 2
- PostgreSQL bootstrapped with required extensions (PostGIS, pgcrypto, uuid-ossp, optional pgvector)
- Base schemas created (e.g., `raw`, `curated`)
- MinIO buckets created (`raw`, `curated`)
- Smoke checks for reachability + bootstrap pass (`smoke_day2.sh`)

### Day 3
- `ingestor-file` can run once:
  - uploads a small CSV to MinIO RAW
  - publishes an `ingest.file` event to Kafka
  - moves the file to `processed/` (or `quarantine/` on failure)
- End-to-end smoke passes (`smoke_day3.sh`)

### Day 4
- Local deterministic HTTP source available via WireMock (`mock-api`)
- `ingestor-http` can run once:
  - fetches a 200 response from the mock API
  - stores the raw payload in MinIO RAW and emits `payload.raw_uri`
  - publishes an `ingest.http` event to Kafka topic `ingest.http.v1`
- End-to-end smoke passes (`smoke_day4.sh`)

### Day 5
- Streaming ingestion validated:
  - `ingestor-stream-producer` generates synthetic messages to Kafka topic `source.posts.v1`
  - `ingestor-stream-consumer` consumes `source.posts.v1` and, **for each message**:
    - stores the raw payload in MinIO RAW as an immutable object
    - emits an `ingest.stream` event to Kafka topic `ingest.stream.v1` including `payload.raw_uri` + `topic/partition/offset`
- End-to-end smoke passes (`smoke_day5.sh`)



## Contracts (important)

All cross-boundary payloads are specified under **`contracts/`**:
- Event envelope JSON Schemas
- Examples (golden files)
- (Optional) AsyncAPI for topics and OpenAPI for Agent endpoints

See:
- `contracts/conventions.md`

---

## Bootstrap / initialization (idempotent)

Infrastructure bootstrap scripts should live under `infra/*` and must be **idempotent**:
- PostgreSQL: create roles/db/extensions (PostGIS, pgvector) + base schemas
- Object storage: create buckets (`raw`, `curated`) + policies
- Kafka: create topics (if used)
- Grafana: provision datasources/dashboards

---

## Troubleshooting

### “Port already in use”
Stop conflicting processes or change the exposed port in `docker-compose.yml`.

### Services start but fail to connect
- Ensure `depends_on` uses `service_healthy` where relevant.
- Prefer service DNS names (e.g., `postgres:5432`) **inside** the compose network.

### Data doesn’t persist
Make sure volumes are defined and mounted correctly. If you reset with `down -v`, persistence is expected to be lost.

---

## Definition of Done (Day 1)

- Platform boots with `docker compose up -d` and becomes **healthy**
- Bootstrap is **idempotent** (reset + up yields the same state)
- `contracts/` exists with envelope schema + a few examples
- README explains how to run, verify, and reset the platform

## Day 6 – SQL Lakehouse (Trino + Hive Metastore + MinIO + dbt)


This day extends the POC with a **repeatable** RAW → STG → CURATED pipeline **inside MinIO**, using:

- **MinIO** (S3-compatible): buckets `raw` and `curated`
- **Hive Metastore (HMS)**: metadata service backed by Postgres (`hms-db`)
- **Trino**: SQL engine with the `hive` catalog to read/write datasets in MinIO
- **dbt (dbt-trino)**: builds STG/CURATED models as versioned SQL

### Why we do it
- Query RAW files immediately (CSV/JSON) without loading into Postgres
- Produce **CURATED Parquet** for efficient analytics and downstream serving
- Make transformations **reproducible** (dbt models + tests + lineage)

### Data zones & locations

**RAW (bucket `raw`)** – immutable landing:
```
s3://raw/source=<file|http|stream>/dt=YYYY-MM-DD/<run-id-or-hash>/
```

**STG/CURATED (bucket `curated`)** – managed datasets:
- `hive.stg_s3` → `s3a://curated/hive/stg/`
- `hive.curated_s3` → `s3a://curated/hive/curated/`

### S3 schemes: `s3a://` vs `s3://` (important)

- **`s3a://`** is the Hadoop filesystem scheme used by Hive/HMS (via Hadoop config).
- **`s3://`** is what Trino commonly expects in `external_location` when creating external tables.

Working pattern in this POC:
- `CREATE SCHEMA ... WITH (location='s3a://...')`  (Hive Metastore / Hadoop)
- `CREATE TABLE ... WITH (external_location='s3://...')` (Trino)

### One-time SQL bootstrap (run in Trino)

Create S3-backed schemas (HMS-managed):

```sql
CREATE SCHEMA IF NOT EXISTS hive.raw_s3
WITH (location='s3a://raw/hive/raw_s3/');

CREATE SCHEMA IF NOT EXISTS hive.stg_s3
WITH (location='s3a://curated/hive/stg/');

CREATE SCHEMA IF NOT EXISTS hive.curated_s3
WITH (location='s3a://curated/hive/curated/');
```

Create RAW external table on top of CSV files (replace `<hash>`):

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
  external_location = 's3://raw/source=file/dt=2026-01-30/<hash>/',
  skip_header_line_count = 1
);
```

### dbt (containerized) – how to run

Typical commands:

```bash
docker compose build dbt
docker compose run --rm dbt debug
docker compose run --rm dbt run
docker compose run --rm dbt test
```

#### dbt connection (`profiles.yml`)
When dbt runs inside Docker, use the Trino service name as `host`:

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

#### Schema mapping + Parquet (`dbt_project.yml`)
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

#### Critical: avoid dbt schema prefixing
By default dbt builds schema names like:

`<target.schema>_<custom.schema>` → e.g. `raw_s3_curated_s3`

That can accidentally fall back to a local `file:` warehouse path and fail with:
`No factory for location: file:/opt/hive/data/warehouse/...`

Fix: override `generate_schema_name`:

`macros/generate_schema_name.sql`
```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
```

### Models built in Day 6

- **STG**: `hive.stg_s3.stg_traffic` (view)
  - type casting (`try_cast`)
  - timestamp parsing for `measured_at_utc`
  - normalize categorical fields (congestion, incident)

- **CURATED**: `hive.curated_s3.fct_traffic_daily` (Parquet)
  - aggregated by day + sensor/city
  - uses `max_by(label, rank)` for max congestion (not string max)

Example pattern for congestion:

```sql
-- in STG: label + rank
upper(trim(congestion_level)) as congestion_level,
case upper(trim(congestion_level))
  when 'LOW' then 1
  when 'MEDIUM' then 2
  when 'HIGH' then 3
  else null
end as congestion_level_rank

-- in CURATED:
max_by(congestion_level, congestion_level_rank) as congestion_level_max
```

### Validation (run in Trino)

```sql
select * from hive.stg_s3.stg_traffic limit 5;
select * from hive.curated_s3.fct_traffic_daily order by traffic_date desc limit 10;
```

### Day 6 troubleshooting

- **`dbt debug` shows `git [ERROR]`**  
  Install `git` in the dbt image (dbt checks it even if you don't use packages yet).

- **`No factory for location: file:...`**  
  Almost always means dbt is targeting an unintended schema (e.g., `raw_s3_curated_s3`).  
  Add the `generate_schema_name` override macro and ensure schemas use S3 locations.

- **S3 “jar hell” in HMS**  
  The working combo used in this POC:
  - `hadoop-common` 3.4.1
  - `hadoop-aws` 3.4.1
  - AWS SDK v2 bundle 2.24.6
    Plus correct `core-site.xml` so HMS can `hadoop fs -ls s3a://...`.


