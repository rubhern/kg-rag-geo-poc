# POC – Data Platform (Ingestion → RAW → Curated → Query/Agent)

This repository contains a **local, docker-compose-based** Proof of Concept to validate an end-to-end flow:
data ingestion from multiple sources, RAW storage, curation, analytics/dashboards, and a conversational/agent layer.

---

## What’s inside (high level)

- **Ingestors**: pull/receive data from sources (file / HTTP / stream).
- **RAW storage**: object storage (e.g., S3-compatible) for immutable raw dumps.
- **Curated storage**: PostgreSQL + PostGIS (and optionally pgvector) for queryable datasets.
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
```

- Day 3 uses `ingestor-file` under the `manual` profile.
- Day 4 uses `mock-api` (WireMock) + `ingestor-http` under the `manual` profile.

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
