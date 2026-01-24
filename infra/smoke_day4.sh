#!/usr/bin/env bash
set -euo pipefail

# Day 4 smoke checks (most robust):
# - Mock API reachable (WireMock)
# - Run ingestor-http once
# - Capture BOTH stdout+stderr from docker compose run into a temp file
# - Extract raw_uri from that file
# - Validate RAW object exists in MinIO
#
# This avoids all the Kafka consumer key formatting issues.

# shellcheck disable=SC1091
source "smoke_common.sh"

require_cmd docker
require_cmd curl
load_dotenv

# MinIO object check (uses minio-init image with mc).
minio_object_exists() {
  local bucket="$1"
  local key="$2"
  docker compose run --rm --entrypoint /bin/sh minio-init -c     "mc alias set local http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}' >/dev/null &&      mc stat local/'${bucket}'/'${key}' >/dev/null"
}

mock_api_reachable() {
  local url="$1"
  curl -sSf "$url" >/dev/null
}

# --- Checks ---
run_check "docker compose ps" docker_compose_ps
run_check "Kafka reachable (list topics)" kafka_reachable
run_check "MinIO live endpoint" minio_live
run_check "MinIO bucket exists: ${MINIO_BUCKET_RAW}" minio_bucket_exists "${MINIO_BUCKET_RAW}"

MOCK_HOST_PORT="${MOCK_HOST_PORT:-8089}"
MOCK_HOST_URL="${MOCK_HOST_URL:-http://localhost:${MOCK_HOST_PORT}/api/merchant-locations}"
run_check "Mock API reachable: ${MOCK_HOST_URL}" mock_api_reachable "${MOCK_HOST_URL}"

# --- End-to-end run (Docker) ---
HTTP_DATASET="${HTTP_DATASET:-merchant_locations}"
HTTP_URL="${HTTP_URL:-http://mock-api:8080/api/merchant-locations}"
TOPIC="${KAFKA_TOPIC_INGEST_HTTP:-ingest.http.v1}"

# Contract mounting (optional): try ./contracts or ../contracts
CONTRACTS_DIR=""
if [[ -d "./contracts" ]]; then
  CONTRACTS_DIR="./contracts"
elif [[ -d "../contracts" ]]; then
  CONTRACTS_DIR="../contracts"
fi

VALIDATE_SCHEMA="${VALIDATE_SCHEMA:-true}"
SCHEMA_PATH="${SCHEMA_PATH:-/contracts/events/ingest-http.v1.schema.json}"

TMP_OUT="$(mktemp -t smoke_day4_ingestor_http.XXXXXX)"
cleanup() { rm -f "$TMP_OUT"; }
trap cleanup EXIT

printf "\n== Running ingestor-http (Docker) ==\n"

if [[ -n "$CONTRACTS_DIR" ]]; then
  # Capture stdout+stderr, and also show it live
  docker compose --profile manual run --rm     -e "RUN_MODE=once"     -e "HTTP_DATASET=${HTTP_DATASET}"     -e "HTTP_URL=${HTTP_URL}"     -e "KAFKA_TOPIC_INGEST_HTTP=${TOPIC}"     -e "VALIDATE_SCHEMA=${VALIDATE_SCHEMA}"     -e "SCHEMA_PATH=${SCHEMA_PATH}"     -v "$(pwd)/${CONTRACTS_DIR}:/contracts:ro"     ingestor-http 2>&1 | tee "$TMP_OUT"
else
  warn "No contracts/ directory found (./contracts or ../contracts). Running without schema mount."
  docker compose --profile manual run --rm     -e "RUN_MODE=once"     -e "HTTP_DATASET=${HTTP_DATASET}"     -e "HTTP_URL=${HTTP_URL}"     -e "KAFKA_TOPIC_INGEST_HTTP=${TOPIC}"     -e "VALIDATE_SCHEMA=false"     ingestor-http 2>&1 | tee "$TMP_OUT"
fi

# Extract raw_uri from the captured output.
# Prefer JSON line with "raw_uri", but regex fallback is enough.
RAW_URI="$(grep -oE 's3://[^[:space:]"'\'' ]+' "$TMP_OUT" | tail -n 1 || true)"

[[ -n "$RAW_URI" ]] || fail "Could not extract raw_uri from ingestor output. Output captured in: ${TMP_OUT}"

ok "raw_uri: ${RAW_URI}"

# Parse s3://bucket/key (no python required)
BUCKET="$(echo "$RAW_URI" | sed -n 's#^s3://\([^/]*\)/.*#\1#p')"
KEY="$(echo "$RAW_URI" | sed -n 's#^s3://[^/]*/\(.*\)$#\1#p')"

[[ -n "$BUCKET" ]] || fail "Could not parse bucket from raw_uri"
[[ -n "$KEY" ]] || fail "Could not parse key from raw_uri"

run_check "MinIO object exists: ${RAW_URI}" minio_object_exists "${BUCKET}" "${KEY}"

printf "\nAll Day 4 smoke checks passed (RAW validated).\n"
