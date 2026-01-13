# ADR-0001: Kafka/Redpanda as event backbone for ingestion events

- Status: **Accepted**
- Date: 2026-01-13

## Context
We need a robust way to decouple producers (ingestors) and consumers (curator, dashboards, agent),
while ensuring cross-boundary data follows **explicit contracts**.

## Decision
Use **Kafka/Redpanda** as the **event backbone** for all ingestion and pipeline lifecycle events:
- Producers publish **validated** contract events (`ingest.file`, `ingest.http`, `ingest.stream`)
- Curator consumes events, processes RAW payloads, then publishes `curate.completed`

RAW payloads remain in object storage; the broker carries **control-plane** messages and pointers.

## Options considered

### A) Kafka/Redpanda as backbone (chosen)
**Pros**
- Decoupling and scalability pattern aligned with production-like architectures
- Natural replay and backpressure handling
- Clear contract boundaries via topics + schemas

**Cons**
- Operational overhead (more moving parts)
- “Exactly once” is not automatic; idempotency still required

### B) No broker, only RAW + polling
**Pros**
- Simpler to boot locally
- Fewer failure modes

**Cons**
- Weaker decoupling
- Harder to support multiple consumers and replays cleanly
- Lifecycle events become ad-hoc

### C) Broker optional (hybrid)
**Pros**
- Best of both worlds for local dev
- Can degrade gracefully

**Cons**
- Two modes to maintain and test

## Consequences
- Producers and consumers must implement:
  - JSON Schema validation
  - Idempotency (e.g., `idempotency_key`, offsets)
  - DLQ/quarantine path for invalid messages
- We define stable topic naming and partitioning strategy.

## Topic conventions (initial)
- `poc.ingest.file`
- `poc.ingest.http`
- `poc.ingest.stream`
- `poc.curate.completed`

## Partitioning recommendation
- Use `dataset` as key for ingestion topics (stable ordering per dataset)
- For stream ingestion, use source key if meaningful; otherwise dataset

## Operational notes
- Add healthchecks and startup retries.
- Provide a smoke test that checks the broker is reachable and topics exist.
