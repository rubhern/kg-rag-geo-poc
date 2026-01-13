# Day 1 – Minimal Architecture (POC)

This document captures the **minimum architecture baseline** for Day 1:
a reproducible local platform that boots reliably and defines the boundaries and contracts.

> (Speculation) Component names and exact ports may differ from your docker-compose. Replace placeholders accordingly.

---

## 1) Goals (Day 1)

- Boot the full platform locally via Docker Compose.
- Establish **system boundaries** and a **contract-first** approach for cross-boundary data.
- Ensure the platform is **repeatable** (idempotent bootstrap) and **observable** enough to debug quickly.

### Non-goals (Day 1)
- Perfect domain modeling
- Full production-grade security/IAM
- Performance optimization
- Comprehensive curated model

---

## 2) Architecture overview

### Main flow
1. Ingestors acquire data (file / HTTP / stream).
2. Ingestors store immutable dumps in **RAW object storage**.
3. Ingestors emit a **validated event** to the event bus (Kafka/Redpanda).
4. Curator consumes events, applies transformations, and writes **Curated** datasets to PostgreSQL/PostGIS.
5. Curator emits a `curate.completed` event (for dashboards/alerting and traceability).
6. Agent/API and dashboards query Curated storage.

---

## 3) System context

See: `docs/diagrams/context.mmd`

---

## 4) Container view

See: `docs/diagrams/containers.mmd`

---

## 5) Contracts & schema governance

Contracts live under `contracts/` and define:
- An **event envelope** shared by all events
- Per-type schemas: `ingest.file`, `ingest.http`, `ingest.stream`, `curate.completed`, `kg.episode` (placeholder)

Rules:
- Producers validate before publishing.
- Consumers validate before processing.
- Invalid messages go to DLQ / quarantine (implementation detail).

See:
- `contracts/conventions.md`
- ADR: `docs/adr/ADR-0002-contracts-json-schema.md`

---

## 6) Event backbone choice

(Recommended) Use Kafka/Redpanda as the **control plane** for ingest/curate events.
RAW object storage remains the **data plane** for raw payloads.

See ADR: `docs/adr/ADR-0001-kafka-event-backbone.md`

---

## 7) Operational baseline (Day 1)

- Health checks for core services (DB, object storage, broker, Grafana)
- A smoke script that verifies connectivity and bootstrap artifacts

See: `docs/operational/smoke-checks.md`

---

## 8) Risks & mitigations (Day 1)

| Risk | Impact | Mitigation |
|---|---|---|
| “Kafka guarantees contracts” misconception | Invalid payloads still appear | Validate on producer and consumer; keep golden examples + CI validation |
| Tight coupling to broker | Platform doesn’t boot reliably | Healthchecks + backoff; allow local mode with broker optional if needed |
| RAW naming inconsistencies | Hard to reproduce / audit | Enforce RAW URI convention in `conventions.md` and validate in ingestors |
| Schema drift | Consumers break silently | SemVer rules + examples validated in CI |

---

## 9) Definition of Done (Day 1)

- `docker compose up -d` results in healthy services
- Idempotent bootstrap: `down -v` then `up` yields same initial state
- Contracts exist and are documented (envelope + per-type + examples)
- Minimal architecture docs exist (this file + diagrams + ADRs)
