from __future__ import annotations

import json
from pathlib import Path
import time
import uuid
from datetime import datetime, timezone

from config import load_config
from http_client import fetch_once
from raw_store import put_raw_json
from event_builder import build_event, build_raw_key, EventInput
from confluent_kafka import Producer
from schema_validation import validate_event


def log_json(message: str, **fields) -> None:
    payload = {"msg": message, **fields}
    print(json.dumps(payload, ensure_ascii=False))


def run_once(cfg) -> None:
    now_utc = datetime.now(timezone.utc)

    # 1) Fetch
    res = fetch_once(cfg.http_url, cfg.http_timeout_seconds)

    # 2) Store RAW
    event_id = str(uuid.uuid4())

    raw_key = build_raw_key(cfg.dataset, "ingestor-http", event_id, now_utc)
    raw_uri = put_raw_json(
        endpoint_url=cfg.s3_endpoint,
        access_key=cfg.s3_access_key,
        secret_key=cfg.s3_secret_key,
        bucket=cfg.s3_bucket_raw,
        key=raw_key,
        body=res.content,
        content_type=res.content_type,
    )

    # 3) Build event (matches ingest-http.v1.schema.json)
    ev = build_event(
        EventInput(
            event_id=event_id,
            dataset=cfg.dataset,
            endpoint=cfg.http_url,
            http_status=res.status,
            raw_uri=raw_uri,
            http_method="GET",
            duration_ms=res.duration_ms,
            rate_limit_remaining=res.rate_limit_remaining,
            cursor=None,
            window_start=None,
            window_end=None,
            env=cfg.env,
            tenant=cfg.tenant,
        )
    )

    if cfg.validate_schema:
        validate_event(Path(cfg.schema_path), ev)

    # 4) Publish Kafka (use idempotency_key as message key)
    producer = Producer({
        "bootstrap.servers": cfg.kafka_bootstrap_servers,
        "client.id": "ingestor-file",
        # Make failures visible fast in a POC
        "socket.timeout.ms": 5000,
        "message.timeout.ms": 10000,
    })
    def delivery_report(err, msg):
        if err is not None:
            raise SystemExit(f"Kafka delivery failed: {err}")
        print(f"✅ Kafka delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

    producer.produce(topic=cfg.kafka_topic, key=ev.get("idempotency_key"), value=json.dumps(ev).encode("utf-8"), callback=delivery_report)
    producer.flush(10)

    log_json(
        "ingest.http done",
        dataset=cfg.dataset,
        http_url=cfg.http_url,
        raw_uri=raw_uri,
        kafka_topic=cfg.kafka_topic,
        http_status=res.status,
        duration_ms=res.duration_ms,
    )


def main() -> None:
    cfg = load_config()
    log_json("ingestor-http starting", run_mode=cfg.run_mode, dataset=cfg.dataset, http_url=cfg.http_url)

    if cfg.run_mode == "once":
        run_once(cfg)
        return

    while True:
        try:
            run_once(cfg)
        except Exception as e:
            log_json("ingestor-http error", error=str(e))
        time.sleep(cfg.poll_seconds)


if __name__ == "__main__":
    main()
