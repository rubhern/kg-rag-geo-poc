# POC – Data Platform (Ingestion → RAW → Curated → Query/Agent)

This repository contains a **local, docker-compose-based** Proof of Concept to validate an end-to-end flow:
**ingestion → immutable RAW storage → (later) curation/query → (later) dashboards/agent**.

This README is maintained **day-by-day**. This version is updated **up to Day 3**.

---

## What’s inside

Core components of the POC (up to Day 3):

- **Object storage (RAW)**: **MinIO** (S3-compatible)
- **Streaming**: **Kafka** + **Kafka UI**
- **Curated storage (ready for later days)**: **PostgreSQL** (and PostGIS-ready)
- **Observability stack**: OpenTelemetry Collector + Prometheus + Loki + Tempo + Grafana
- **Run-once ingestor** (Day 3): `services/ingestor-file` (Python)

---

## Quickstart

> Run commands from the folder where `docker-compose.yml` and `.env` live.

### Prerequisites

- Docker Engine + Docker Compose plugin
- Bash-compatible shell for smoke scripts (Git Bash / WSL is fine on Windows)

### 1) Configure environment

If you already have a `.env`, you can skip this step.

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

You should see services in `running` state and (where configured) `healthy`.

### 4) Stop the platform

```bash
docker compose down
```

### 5) Full reset (⚠️ destroys volumes)

```bash
docker compose down -v
```

---

## Endpoints

Ports are configured through `.env` (defaults shown below).

| Component                  |                 Default | Notes                                 |
|----------------------------|------------------------:|---------------------------------------|
| PostgreSQL                 |        `localhost:5432` | DB `poc`, user `poc` (see `.env`)     |
| MinIO (S3 API)             | `http://localhost:9000` | RAW/curated buckets                   |
| MinIO Console              | `http://localhost:9001` | Login with `MINIO_ROOT_USER/PASSWORD` |
| Kafka (host access)        |       `localhost:29092` | Use this from your host machine       |
| Kafka UI                   | `http://localhost:8080` | Browse topics/messages                |
| Grafana                    | `http://localhost:3000` | user/pass: `admin/admin` (POC)        |
| Prometheus                 | `http://localhost:9090` | Metrics                               |
| Loki                       | `http://localhost:3100` | Logs                                  |
| Tempo                      | `http://localhost:3200` | Traces                                |
| OTEL Collector (gRPC/HTTP) |             `4317/4318` | OTLP ingest                           |

---

## Contracts (important)

All cross-boundary payloads are specified under **`contracts/`**.

Up to Day 3, the relevant JSON Schemas are:

- `contracts/events/envelope.v1.schema.json` – base envelope (strict root, `additionalProperties: false`)
- `contracts/events/ingest-file.v1.schema.json` – file ingestion event (extends envelope via `allOf`)

Conventions and examples:

- `contracts/conventions.md`
- `contracts/examples/*`

---

## Day-by-day

### Day 1 — Platform skeleton + bootstrap

Goal: bring up the local platform with Docker Compose and ensure repeatable bootstrap.

Deliverables:

- `docker compose up -d` yields a healthy stack
- MinIO and buckets exist (`raw`, `curated`) via `minio-init`
- Kafka is reachable
- Contracts folder exists (at least the envelope schema + examples)

Smoke test:

- `smoke_day1.sh`

### Day 2 — Contracts + conventions + bootstrap verification

Goal: lock down cross-boundary contracts and verify bootstrap state.

Deliverables:

- Envelope schema + ingestion schemas in `contracts/events/`
- Naming/versioning conventions in `contracts/conventions.md`
- “Golden” examples in `contracts/examples/`

Smoke test:

- `smoke_day2.sh` (extends Day 1 with bootstrap checks)

### Day 3 — End-to-end run-once ingestion (file → RAW → Kafka → processed/quarantine)

Goal: implement and validate the first ingestion pipeline for **files**.

#### Input → processing model

- Input files are provided to the ingestor under `/incoming` (container path)
- On success, the input is moved to `/processed`
- On failure, the input is moved to `/quarantine/<stem>/` with `reason.txt`

#### RAW storage convention (MinIO)

- Bucket: `${MINIO_BUCKET_RAW}` (default: `raw`)
- Object key:

```text
source=<source>/dt=<YYYY-MM-DD>/<sha256>/<filename>
```

Where:

- `source` is a short identifier (e.g., `file`, `http`)
- `dt` is the logical partition date (ingestion date for the POC)
- `sha256` provides idempotency + traceability

#### Kafka event contract (what gets published)

- Topic: `ingest.file.v1` (override via `KAFKA_TOPIC`)
- Key: `idempotency_key` (SHA-256)
- Value: full JSON event (`envelope.v1` + `ingest.file` payload)

Key fields (high level):

- `event_type`: `ingest.file`
- `schema_version`: `1.0.0`
- `idempotency_key`: SHA-256
- `payload` includes:
    - `dataset` (POC: derived from filename unless explicitly set)
    - `raw_uri` (`s3://raw/<key>`)
    - `content_type`: `csv|json|geojson`
    - `checksum` (SHA-256)
    - `source_file_name`

#### Run the ingestor (Docker)

1) Ensure the platform is running:

```bash
docker compose up -d
```

2) Put an example file in the host folder mounted as `/incoming`.

3) Run the ingestor (profile `manual`):

```bash
docker compose --profile manual run --rm \
  ingestor-file \
  --input /incoming/example.csv \
  --dt 2026-01-20
```

Notes:

- Inside Docker network:
    - Kafka bootstrap is `kafka:9092`
    - MinIO endpoint is `http://minio:9000`
- From your host machine (Windows/macOS/Linux):
    - Kafka bootstrap is `localhost:29092`
    - MinIO endpoint is `http://localhost:<MINIO_PORT>`

Smoke test:

- `smoke_day3.sh` (Day 2 + end-to-end run-once ingestion)

---

## Smoke checks

- `SMOKE_README.md` explains all smoke scripts.

Typical run (from the folder where `docker-compose.yml` and `.env` live):

```bash
chmod +x smoke_*.sh
./smoke_day1.sh
./smoke_day2.sh
./smoke_day3.sh
```

---

## Troubleshooting

### Host vs container endpoints (most common pitfall)

- From **host**:
    - Kafka: `localhost:29092`
    - MinIO: `http://localhost:<MINIO_PORT>`

- From **containers**:
    - Kafka: `kafka:9092`
    - MinIO: `http://minio:9000`

### “Port already in use” (Windows)

If a port is occupied on the host (e.g., `9000`), change it in `.env` (e.g., `MINIO_PORT=9002`) and recreate services:

```bash
docker compose up -d --force-recreate
```

### Files not moving to processed/quarantine

- Ensure `/incoming` is mounted **read-write** when the ingestor must move files.
- In Docker runs, you can force output dirs with:
    - `PROCESSED_DIR=/processed`
    - `QUARANTINE_DIR=/quarantine`

---

## Definition of Done

### Day 1

- Platform boots with `docker compose up -d` and becomes **healthy**
- Bootstrap is **idempotent** (reset + up yields the same state)
- `contracts/` exists with envelope schema + examples
- README explains how to run, verify, and reset

### Day 2

- Contracts folder includes envelope + ingestion schemas + examples
- Conventions are documented in `contracts/conventions.md`
- `smoke_day2.sh` passes

### Day 3

- `ingestor-file` builds the event and validates it against JSON Schema
- Upload to MinIO RAW works and object is verifiable
- Kafka publish works and message is visible in Kafka UI
- Input file ends in `processed` on success and `quarantine` on failure
- `smoke_day3.sh` passes
