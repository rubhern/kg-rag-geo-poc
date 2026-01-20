import argparse
import hashlib
import os
import json
import mimetypes
import uuid
import boto3
import shutil

from botocore.config import Config
from botocore.exceptions import ClientError

from jsonschema import RefResolver
from jsonschema.validators import validator_for
from datetime import date, datetime, timezone
from pathlib import Path
from confluent_kafka import Producer


def main() -> int:
    parser = argparse.ArgumentParser(description="POC file ingestor (run-once)")
    parser.add_argument("--input", required=True, help="Path to the input file inside the container (e.g., /incoming/example.csv)")
    parser.add_argument("--dt", default=str(date.today()), help="Business date for RAW partition (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to MinIO/Kafka; just print what would happen.")
    args = parser.parse_args()

    source = os.getenv("SOURCE", "file")
    input_path = args.input

    if not os.path.isfile(input_path):
        raise SystemExit(f"Input file does not exist: {input_path}")

    original_name = os.path.basename(input_path)
    dataset = os.getenv("DATASET", Path(original_name).stem)
    if len(dataset) < 2:
        raise SystemExit("Dataset must have at least 2 characters (set DATASET env var or use a longer file name).")
    sha = sha256_file(input_path)
    raw_key = build_raw_key(source, args.dt, sha, original_name)

    raw_bucket = os.getenv("MINIO_BUCKET_RAW", "raw")
    raw_uri = f"s3://{raw_bucket}/{raw_key}"

    ctype = contract_content_type(input_path)

    meta = {
        "source": source,
        "dataset": dataset,
        "original_name": original_name,
        "sha256": sha,
        "raw_uri": raw_uri,
        "raw_bucket": raw_bucket,
        "raw_key": raw_key,
        "content_type": ctype,
        "ingest_time": now_utc_iso(),
        "event_time": now_utc_iso(),
    }

    event = build_ingest_event(meta)

    schema_path = Path(os.getenv("EVENT_SCHEMA_PATH", "./contracts/events/ingest-file.v1.schema.json"))
    validate_event_against_schema(event, schema_path)

    print("== Ingest plan ==")
    print(json.dumps(event, indent=2))

    if args.dry_run:
        print("dry_run      : true (no MinIO/Kafka writes)")
        return 0

    try:
        # 1) Upload to RAW
        s3 = build_s3_client_from_env()
        ensure_bucket_exists(s3, meta["raw_bucket"])
        upload_to_minio_raw(s3, meta["raw_bucket"], meta["raw_key"], input_path)

        # 2) Publish event to Kafka
        publish_kafka_event(event)

        # 3) Mark processed
        move_to_processed(input_path)
        return 0

    except Exception as e:
        # In a POC we keep it simple: quarantine on any failure
        move_to_quarantine(input_path, str(e))
        raise

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sanitize_filename(name: str) -> str:
    # Keep it simple for the POC; improve later (spaces, unicode, etc.)
    return name.replace("\\", "_").replace("/", "_").strip()

def build_raw_key(source: str, dt: str, sha: str, original_name: str) -> str:
    return f"source={source}/dt={dt}/{sha}/{sanitize_filename(original_name)}"

def guess_content_type(path: str) -> str:
    ct, _ = mimetypes.guess_type(path)
    return ct or "application/octet-stream"

def contract_content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext == ".geojson":
        return "geojson"
    if ext == ".json":
        return "json"
    raise SystemExit(f"Unsupported file extension for contract content_type: {ext}")

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def build_ingest_event(meta: dict) -> dict:
    payload = {
        "dataset": meta["dataset"],
        "raw_uri": meta["raw_uri"],
        "content_type": meta["content_type"],
        "checksum": meta["sha256"],
        "source_file_name": meta["original_name"],
    }

    # Optional: only include if you have an integer
    if "record_count" in meta and isinstance(meta["record_count"], int):
        payload["record_count"] = meta["record_count"]

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "ingest.file",
        "schema_version": "1.0.0",
        "source": meta["source"],
        "event_time": meta["event_time"],
        "ingest_time": meta["ingest_time"],
        "idempotency_key": meta["sha256"],
        "payload": payload,
    }

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_event_against_schema(event: dict, schema_path: Path) -> None:
    if not schema_path.exists():
        raise SystemExit(f"Schema file not found: {schema_path}")

    schema = load_json(schema_path)

    # Base URI for resolving local $ref, allOf, etc.
    base_dir = schema_path.parent
    store: dict[str, dict] = {}

    # Load the envelope schema (required by ingest-file.v1.schema.json)
    envelope_path = base_dir / "envelope.v1.schema.json"
    if envelope_path.exists():
        envelope_schema = load_json(envelope_path)

        # Map by $id (https://example.local/...) so remote resolution is satisfied locally
        if "$id" in envelope_schema:
            store[envelope_schema["$id"]] = envelope_schema

        # Also map by file:// URI (useful if refs resolve to file URIs)
        store[envelope_path.resolve().as_uri()] = envelope_schema

    # Map the main schema too (same idea)
    if "$id" in schema:
        store[schema["$id"]] = schema
    store[schema_path.resolve().as_uri()] = schema

    # Base URI for resolving relative refs (envelope.v1.schema.json)
    base_uri = base_dir.resolve().as_uri() + "/"
    resolver = RefResolver(base_uri=base_uri, referrer=schema, store=store)

    Validator = validator_for(schema)
    validator = Validator(schema, resolver=resolver)

    errors = sorted(validator.iter_errors(event), key=lambda e: list(e.path))
    if errors:
        print("❌ Event validation failed:")
        for err in errors:
            where = ".".join([str(p) for p in err.path]) or "<root>"
            print(f" - {where}: {err.message}")
        raise SystemExit(2)

    print("✅ Event validated against JSON Schema")

def upload_to_minio_raw(s3, bucket: str, key: str, file_path: str) -> None:
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    print(f"Uploading to MinIO: s3://{bucket}/{key}")
    s3.upload_file(
        Filename=file_path,
        Bucket=bucket,
        Key=key,
        ExtraArgs={"ContentType": mime_type},
    )
    print("✅ Upload completed")

def build_s3_client_from_env():
    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")

    if not access_key or not secret_key:
        raise SystemExit("MINIO_ACCESS_KEY / MINIO_SECRET_KEY must be set")

    # MinIO works best with path-style addressing in local/dev setups
    cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"})

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=cfg,
    )


def ensure_bucket_exists(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        # In MinIO you may see 404/NoSuchBucket depending on client behavior
        if code not in ("404", "NoSuchBucket", "NotFound"):
            raise

    print(f"Bucket '{bucket}' not found. Creating it...")
    s3.create_bucket(Bucket=bucket)

def publish_kafka_event(event: dict) -> None:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC", "ingest.file.v1")

    producer = Producer({
        "bootstrap.servers": bootstrap,
        "client.id": "ingestor-file",
        # Make failures visible fast in a POC
        "socket.timeout.ms": 5000,
        "message.timeout.ms": 10000,
    })

    key = event.get("idempotency_key", "")
    value = json.dumps(event).encode("utf-8")

    def delivery_report(err, msg):
        if err is not None:
            raise SystemExit(f"Kafka delivery failed: {err}")
        print(f"✅ Kafka delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

    producer.produce(topic=topic, key=key, value=value, callback=delivery_report)
    producer.flush(10)

def move_to_processed(input_path: str) -> None:
    src = Path(input_path)
    dst = Path("/processed") / src.name
    shutil.move(str(src), str(dst))
    print(f"✅ Moved to processed: {dst}")

def move_to_quarantine(input_path: str, reason: str) -> None:
    src = Path(input_path)
    qdir = Path("/quarantine") / src.stem
    qdir.mkdir(parents=True, exist_ok=True)

    dst_file = qdir / src.name
    shutil.move(str(src), str(dst_file))

    (qdir / "reason.txt").write_text(reason, encoding="utf-8")
    print(f"⚠️ Moved to quarantine: {dst_file}")
    print(f"⚠️ Reason: {reason}")

if __name__ == "__main__":
    raise SystemExit(main())
