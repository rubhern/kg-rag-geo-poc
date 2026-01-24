import io
import json
import os
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, Producer, KafkaException
from minio import Minio


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_ymd_parts() -> tuple[str, str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")


def safe_decode_key(key_bytes) -> str | None:
    if key_bytes is None:
        return None
    try:
        return key_bytes.decode("utf-8")
    except Exception:
        # Fallback for non-utf8 keys
        return str(key_bytes)


def build_object_names(dataset: str, event_id: str) -> tuple[str, str]:
    """
    Conventions.md suggests:
      raw/{dataset}/{yyyy}/{mm}/{dd}/{source}/{event_id}/payload.<ext>
      raw/{dataset}/{yyyy}/{mm}/{dd}/{source}/{event_id}/metadata.json

    For MinIO object_name we omit the leading 'raw/' because bucket already is 'raw'.
    """
    yyyy, mm, dd = utc_ymd_parts()
    base = f"{dataset}/{yyyy}/{mm}/{dd}/ingestor-stream/{event_id}"
    return f"{base}/payload.json", f"{base}/metadata.json"


def delivery_report(err, msg) -> None:
    if err is not None:
        print(json.dumps({
            "msg": "ingest.stream delivery failed",
            "error": str(err),
            "topic": msg.topic(),
        }))
    else:
        # Useful when debugging, but can be noisy; keep for POC
        print(json.dumps({
            "msg": "ingest.stream delivered",
            "topic": msg.topic(),
            "partition": msg.partition(),
            "offset": msg.offset(),
        }))


def main() -> None:
    # ---- Kafka config ----
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic_source = os.getenv("KAFKA_TOPIC_SOURCE", "source.posts.v1")
    topic_ingest = os.getenv("KAFKA_TOPIC_INGEST", "ingest.stream.v1")
    group_id = os.getenv("KAFKA_GROUP_ID", "ingestor-stream.v1")

    # ---- MinIO config ----
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_bucket_raw = os.getenv("MINIO_BUCKET_RAW", "raw")
    minio_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # ---- Defaults ----
    default_dataset = os.getenv("DATASET", "posts")
    env_tag = os.getenv("ENV", "local")
    fail_on_bad_json = os.getenv("FAIL_ON_BAD_JSON", "false").lower() == "true"

    # MinIO client
    minio = Minio(
        minio_endpoint,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=minio_secure,
    )

    # Ensure bucket exists (safe for local POC)
    if not minio.bucket_exists(minio_bucket_raw):
        minio.make_bucket(minio_bucket_raw)

    # Kafka consumer
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([topic_source])

    # Kafka producer (for ingest.stream events)
    producer = Producer({
        "bootstrap.servers": bootstrap,
        "acks": "1",
        "retries": 5,
        "linger.ms": 20,
        "compression.type": "snappy",
    })

    print(json.dumps({
        "msg": "ingestor-stream started",
        "topic_source": topic_source,
        "topic_ingest": topic_ingest,
        "group_id": group_id,
        "minio_bucket_raw": minio_bucket_raw,
    }))

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                producer.poll(0)
                continue
            if msg.error():
                raise KafkaException(msg.error())

            ingest_time = utc_now_iso()

            # 1) Parse source message (JSON)
            try:
                source_payload = json.loads(msg.value().decode("utf-8"))
            except Exception as e:
                print(json.dumps({
                    "msg": "bad json in source message",
                    "error": str(e),
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                }))
                if fail_on_bad_json:
                    break
                # Commit to avoid being stuck on a poison-pill message (POC choice)
                consumer.commit(message=msg, asynchronous=False)
                continue

            dataset = source_payload.get("dataset") or default_dataset
            source_event_time = source_payload.get("event_time") or ingest_time
            source_event_id = source_payload.get("source_event_id")  # optional

            # 2) Persist RAW to MinIO (one object per message)
            event_id = str(uuid.uuid4())
            object_payload, object_metadata = build_object_names(dataset, event_id)

            payload_bytes = json.dumps(source_payload).encode("utf-8")
            meta = {
                "dataset": dataset,
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "key": safe_decode_key(msg.key()),
                "source_event_id": source_event_id,
                "event_id": event_id,
                "event_time": source_event_time,
                "ingest_time": ingest_time,
            }
            meta_bytes = json.dumps(meta).encode("utf-8")

            # Upload payload.json
            minio.put_object(
                minio_bucket_raw,
                object_payload,
                io.BytesIO(payload_bytes),
                length=len(payload_bytes),
                content_type="application/json",
            )
            # Upload metadata.json (optional but very useful)
            minio.put_object(
                minio_bucket_raw,
                object_metadata,
                io.BytesIO(meta_bytes),
                length=len(meta_bytes),
                content_type="application/json",
            )

            raw_uri = f"s3://{minio_bucket_raw}/{object_payload}"

            # 3) Emit ingest.stream event (envelope + payload)
            idempotency_key = f"ingest-stream:{msg.topic()}:{msg.partition()}:{msg.offset()}"

            ingest_event = {
                "event_id": event_id,
                "event_type": "ingest.stream",
                "schema_version": "1.0.0",
                "source": "ingestor-stream",
                "event_time": source_event_time,
                "ingest_time": ingest_time,
                "idempotency_key": idempotency_key,
                "tags": {"env": env_tag},
                "payload": {
                    "dataset": dataset,
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": safe_decode_key(msg.key()),
                    "raw_uri": raw_uri,
                    **({"source_event_id": source_event_id} if isinstance(source_event_id, str) else {}),
                },
            }

            # Produce + wait delivery (simple & safe for POC)
            producer.produce(
                topic=topic_ingest,
                key=(safe_decode_key(msg.key()) or "").encode("utf-8"),
                value=json.dumps(ingest_event).encode("utf-8"),
                on_delivery=delivery_report,
            )
            producer.flush(10)

            # 4) Commit source offset only after RAW + event are done
            consumer.commit(message=msg, asynchronous=False)

            # Smoke-friendly log line (raw_uri is easy to grep)
            print(json.dumps({
                "msg": "ingest.stream done",
                "dataset": dataset,
                "kafka_topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "raw_uri": raw_uri,
            }))

    finally:
        try:
            producer.flush(5)
        finally:
            consumer.close()


if __name__ == "__main__":
    main()
