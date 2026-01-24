from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    # JSON Schema expects date-time; "Z" is fine
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_raw_key(dataset: str, source: str, event_id: str, now_utc: datetime) -> str:
    # Matches your example layout:
    # s3://raw/<dataset>/YYYY/MM/DD/<source>/<event_id>/payload.json
    y = now_utc.strftime("%Y")
    m = now_utc.strftime("%m")
    d = now_utc.strftime("%d")
    return f"{dataset}/{y}/{m}/{d}/{source}/{event_id}/payload.json"


@dataclass(frozen=True)
class EventInput:
    event_id: str
    dataset: str
    endpoint: str
    http_status: int
    raw_uri: str
    http_method: str
    duration_ms: int
    rate_limit_remaining: int | None
    cursor: str | None
    window_start: str | None
    window_end: str | None
    env: str
    tenant: str


def build_event(inp: EventInput) -> dict:
    event_time = utc_now_iso()
    ingest_time = utc_now_iso()

    # Simple idempotency: dataset + endpoint (+ cursor if you later add it)
    cursor_part = f":cursor={inp.cursor}" if inp.cursor else ""
    idempotency_key = f"ingest-http:{inp.dataset}:{inp.endpoint}{cursor_part}"

    event = {
        "event_id": inp.event_id,
        "event_type": "ingest.http",
        "schema_version": "1.0.0",
        "source": "ingestor-http",
        "event_time": event_time,
        "ingest_time": ingest_time,
        "idempotency_key": idempotency_key,
        "tags": {
            "env": inp.env,
            "tenant": inp.tenant,
        },
        "payload": {
            "dataset": inp.dataset,
            "endpoint": inp.endpoint,
            "http_method": inp.http_method,
            "http_status": inp.http_status,
            "raw_uri": inp.raw_uri,
            "duration_ms": inp.duration_ms,
        },
    }

    if inp.rate_limit_remaining is not None:
        event["payload"]["rate_limit_remaining"] = inp.rate_limit_remaining
    if inp.cursor is not None:
        event["payload"]["cursor"] = inp.cursor
    if inp.window_start is not None:
        event["payload"]["window_start"] = inp.window_start
    if inp.window_end is not None:
        event["payload"]["window_end"] = inp.window_end

    return event
