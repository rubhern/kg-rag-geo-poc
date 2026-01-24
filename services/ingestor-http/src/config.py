from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    # Ingest
    dataset: str
    http_url: str
    http_timeout_seconds: int
    poll_seconds: int
    run_mode: str  # "once" or "loop"

    # Storage (MinIO/S3)
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_raw: str

    # Kafka
    kafka_bootstrap_servers: str
    kafka_topic: str

    # Metadata
    env: str
    tenant: str

    # Validation (optional)
    validate_schema: bool
    schema_path: str


def _get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or str(val).strip() == "":
        raise ValueError(f"Missing required env var: {name}")
    return str(val).strip()


def load_config() -> Config:
    # Prefer explicit MINIO_ACCESS_KEY/MINIO_SECRET_KEY but fallback to MINIO_ROOT_* (common in MinIO)
    access_key = os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER")
    secret_key = os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD")
    if not access_key or not secret_key:
        raise ValueError("Missing MinIO credentials. Set MINIO_ACCESS_KEY/MINIO_SECRET_KEY or MINIO_ROOT_USER/MINIO_ROOT_PASSWORD.")

    run_mode = os.getenv("RUN_MODE", "loop").strip().lower()
    if run_mode not in ("once", "loop"):
        raise ValueError("RUN_MODE must be 'once' or 'loop'")

    validate_schema = os.getenv("VALIDATE_SCHEMA", "false").strip().lower() in ("1", "true", "yes")

    return Config(
        dataset=_get_env("HTTP_DATASET", "merchant_locations"),
        http_url=_get_env("HTTP_URL"),
        http_timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "10")),
        poll_seconds=int(os.getenv("HTTP_POLL_SECONDS", "60")),
        run_mode=run_mode,

        s3_endpoint=_get_env("MINIO_ENDPOINT", "http://minio:9000"),
        s3_access_key=access_key,
        s3_secret_key=secret_key,
        s3_bucket_raw=_get_env("MINIO_BUCKET_RAW", "raw"),

        kafka_bootstrap_servers=_get_env("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        kafka_topic=_get_env("KAFKA_TOPIC_INGEST_HTTP", "ingest.http.v1"),

        env=os.getenv("ENV", "local"),
        tenant=os.getenv("TENANT", "demo"),

        validate_schema=validate_schema,
        schema_path=os.getenv("SCHEMA_PATH", "/contracts/events/ingest-http.v1.schema.json"),
    )
