# ADR-0002: JSON Schema contracts for event payloads

- Status: **Accepted**
- Date: 2026-01-13

## Context
We need a lightweight, language-agnostic way to define and validate event shapes for:
- ingestion events
- pipeline lifecycle events
- (later) knowledge graph extraction

## Decision
Use **JSON Schema (draft 2020-12)**:
- A shared `EventEnvelopeV1`
- Per-type schemas via `allOf` composition:
  - `ingest.file`, `ingest.http`, `ingest.stream`
  - `curate.completed`
  - `kg.episode` (placeholder)

## Why `allOf`
`allOf` means the instance must satisfy **all** referenced schemas.
We use it to compose:
- the base envelope + the specific payload constraints for each event type

## Consequences
- Schemas must be resolvable (local references or `$id`-based resolution)
- CI should validate golden examples under `contracts/examples/`
- Versioning follows SemVer rules documented in `contracts/conventions.md`
