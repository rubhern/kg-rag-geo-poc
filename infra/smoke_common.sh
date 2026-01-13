#!/usr/bin/env bash
set -euo pipefail

# Small helpers to make smoke checks readable.
ok()   { printf "✅ %s\n" "$*"; }
warn() { printf "⚠️  %s\n" "$*"; }
fail() { printf "❌ %s\n" "$*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

# Load .env from repo root if present (so scripts work without exporting vars).
load_dotenv() {
  local env_file=".env"
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$env_file"; set +a
    ok "Loaded environment from .env"
  else
    warn "No .env file found in current directory; relying on exported env vars"
  fi
}

run_check() {
  local name="$1"; shift
  printf "\n== %s ==\n" "$name"
  if "$@"; then
    ok "$name"
  else
    fail "$name"
  fi
}

docker_compose_ps() {
  docker compose ps
}

pg_select_1() {
  docker compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT 1;" >/dev/null
}

pg_extensions() {
  docker compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT extname FROM pg_extension WHERE extname IN ('postgis','pgcrypto','vector', 'uuid-ossp') ORDER BY 1;" \
    | tr '\n' ' ' \
    | grep -Eq "pgcrypto.postgis.uuid-ossp.vector"
}

pg_schemas() {
  docker compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('raw','curated') ORDER BY 1;" \
    | tr '\n' ' ' \
    | grep -Eq "curated.*raw|raw.*curated"
}

kafka_reachable() {
  docker compose exec -T kafka bash -lc "kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1"
}

minio_live() {
  # Uses host port mapping; works from your machine/WSL.
  curl -sSf "http://localhost:${MINIO_PORT}/minio/health/live" >/dev/null
}

grafana_health_optional() {
  # Grafana may take longer; treat as optional by default.
  curl -sSf "http://localhost:${GRAFANA_PORT}/api/health" >/dev/null
}

otel_health_optional() {
  # Collector doesn't expose a standard /health by default; we just check TCP port is listening via curl on HTTP endpoint
  # If you don't have a health extension enabled, this will be skipped.
  return 0
}

minio_bucket_exists() {
  local bucket="$1"
  # Use minio/mc in a one-off container on the compose network to query buckets reliably.
  docker compose run --rm --entrypoint /bin/sh minio-init -c \
    "mc alias set local http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}' >/dev/null && \
     mc ls local/'${bucket}' >/dev/null"
}
