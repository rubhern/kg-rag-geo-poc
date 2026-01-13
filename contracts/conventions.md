# Contracts Conventions (POC)

This document defines the **rules of the road** for any data that crosses a boundary:
ingestors → RAW, streaming events, curation outputs, and agent/API responses.

These conventions are intentionally **boring**: stable, explicit, and easy to evolve.

---

## 1) Naming

### Dataset names
- Use `snake_case`
- Must be stable identifiers (avoid dates inside dataset names)
- Examples: `traffic_incidents`, `merchant_locations`, `atm_events`

### Event types
- Use dotted names: `domain.action`
- Examples:
  - `ingest.file`
  - `ingest.http`
  - `ingest.stream`
  - `curate.completed`
  - `kg.episode`

---

## 2) Time and IDs

### Timestamps
- Always ISO-8601 **UTC**: `YYYY-MM-DDTHH:mm:ssZ`
- Distinguish:
  - `event_time`: when it happened at the source (best effort)
  - `ingest_time`: when we ingested it (system time)

### Identifiers
- `event_id`: UUID v4 (string)
- If a source already has an ID, include `source_event_id` in the payload.

---

## 3) Schema versioning

### `schema_version`
- Use SemVer: `MAJOR.MINOR.PATCH`
- Rules:
  - PATCH: typo/docs change or non-functional schema metadata updates
  - MINOR: **add optional fields** only (backward compatible)
  - MAJOR: breaking changes (rename fields, change meaning/type, make optional → required)

### Breaking changes
When breaking is required:
- Either increment MAJOR and update consumers
- Or define a new `event_type` (e.g., `ingest.file.v2`) if you want side-by-side support

---

## 4) Envelope (mandatory fields)

All events must conform to the **Event Envelope** (see `contracts/events/envelope.v1.schema.json`).

Required top-level fields:
- `event_id`
- `event_type`
- `schema_version`
- `source`
- `event_time`
- `ingest_time`
- `payload`

Optional but recommended:
- `idempotency_key`
- `trace.trace_id`, `trace.span_id`
- `tags` (string map)

---

## 5) Idempotency (required for ingestion)

### Why
POCs become production prototypes quickly. Idempotency prevents:
- duplicate writes
- duplicated side effects
- “it worked locally” inconsistencies

### `idempotency_key`
- A stable string that identifies the operation uniquely.
- Must be deterministic from source inputs.

Examples:
- File ingestion:
  - `ingest-file:{dataset}:{yyyy-mm-dd}:{source_file_name}`
- HTTP ingestion:
  - `ingest-http:{dataset}:{endpoint}:{cursor_or_date}`
- Stream ingestion:
  - `ingest-stream:{topic}:{partition}:{offset}` (or upstream event id)

---

## 6) RAW storage conventions (object storage)

### Buckets
- `raw`: immutable dumps
- `curated`: optional exports (if you export curated snapshots)

### RAW object naming
Recommended pattern:
```text
raw/{dataset}/{yyyy}/{mm}/{dd}/{source}/{event_id}/payload.<ext>
raw/{dataset}/{yyyy}/{mm}/{dd}/{source}/{event_id}/metadata.json
```

Rules:
- RAW objects are append-only (no in-place updates)
- Any derived or cleaned form belongs to **curated** layers

---

## 7) Curated layer conventions (PostgreSQL/PostGIS)

### Schema naming
- Use a dedicated schema for curated data, e.g. `curated`
- If multi-tenant in the future, avoid tenant-specific schemas unless necessary.

### Geometry
- Prefer WGS84 (EPSG:4326) unless there is a clear reason otherwise
- Store geometry as `geometry` type and index it (GiST)

### Primary keys
- Prefer stable natural keys if they exist; otherwise use UUIDs
- For time-series, consider composite keys: `{entity_id, event_time}`

---

## 8) Observability propagation

If your platform includes tracing:
- Include `trace.trace_id` and `trace.span_id` in the envelope when available
- Propagate trace context across services and include it in logs

---

## 9) Validation

### Golden examples
Store representative, validated examples under `contracts/examples/`.

### CI recommendation
Add a simple CI job to:
- validate JSON examples against JSON Schemas
- fail fast when a contract is accidentally broken

---

## 10) Non-goals (for Day 1)
- Perfect domain modeling
- Full backward-compatibility matrix
- Complete OpenAPI/AsyncAPI coverage

For Day 1, the goal is a **stable baseline** that will not collapse under iteration.
