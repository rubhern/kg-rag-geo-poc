#!/usr/bin/env bash
set -euo pipefail

# Day 3 smoke checks: Day 2 + end-to-end ingestion run-once
# - Uploads a small CSV to MinIO RAW
# - Publishes an ingest.file event to Kafka
# - Moves the input file to processed (or quarantine on failure)
#
# Run from the repo infra path (same folder where docker-compose.yml and .env live).

# shellcheck disable=SC1091
source "smoke_common.sh"

require_cmd docker
require_cmd curl
load_dotenv

# Optional dependencies (we have fallbacks)

sha256_of_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<PY
import hashlib
p = r"$file"
h = hashlib.sha256()
with open(p, "rb") as f:
    for chunk in iter(lambda: f.read(1024*1024), b""):
        h.update(chunk)
print(h.hexdigest())
PY
    return 0
  fi
  fail "Missing sha256sum or python3 to compute SHA-256"
}

# MinIO object check (uses minio-init image with mc).
minio_object_exists() {
  local bucket="$1"
  local key="$2"
  docker compose run --rm --entrypoint /bin/sh minio-init -c \
    "mc alias set local http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}' >/dev/null && \
     mc stat local/'${bucket}'/'${key}' >/dev/null"
}

# Kafka check: confirm we can find our message (by sha) in the topic.
# Assumption for POC: low traffic topic; scanning the last few messages per partition is enough.
kafka_topic_contains_sha() {
  local topic="$1"
  local sha="$2"

  local offsets
  offsets=$(docker compose exec -T kafka bash -lc \
    "kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic '${topic}' --time -1" 2>/dev/null || true)

  [[ -n "$offsets" ]] || return 1

  while IFS=: read -r t p o; do
    [[ -n "${p:-}" ]] || continue
    [[ -n "${o:-}" ]] || continue

    # read last few messages (max 10) from each partition
    local start
    if [[ "$o" =~ ^[0-9]+$ ]] && (( o > 5 )); then
      start=$((o - 5))
    else
      start=0
    fi

    local out
    out=$(docker compose exec -T kafka bash -lc \
      "kafka-console-consumer \
        --bootstrap-server localhost:9092 \
        --topic '${topic}' \
        --partition '${p}' \
        --offset '${start}' \
        --max-messages 10 \
        --timeout-ms 5000 \
        --property print.key=true \
        --property key.separator='|'" 2>/dev/null || true)

    # In this POC we use sha256 as idempotency_key (and Kafka key). Match either key or payload.
    if echo "$out" | grep -q "^${sha}|"; then
      return 0
    fi
    if echo "$out" | grep -q "${sha}"; then
      return 0
    fi
  done <<< "$offsets"

  return 1
}

# --- Checks ---
run_check "docker compose ps" docker_compose_ps
run_check "Kafka reachable (list topics)" kafka_reachable
run_check "MinIO live endpoint" minio_live
run_check "MinIO bucket exists: ${MINIO_BUCKET_RAW}" minio_bucket_exists "${MINIO_BUCKET_RAW}"

# --- End-to-end run ---
# Use a dedicated, local smoke workspace so this doesn't interfere with your real data folders.
SMOKE_ROOT="${SMOKE_ROOT:-.}"
INCOMING_DIR="${SMOKE_INCOMING_DIR:-${SMOKE_ROOT}/incoming}"
PROCESSED_DIR="${SMOKE_PROCESSED_DIR:-${SMOKE_ROOT}/processed}"
QUARANTINE_DIR="${SMOKE_QUARANTINE_DIR:-${SMOKE_ROOT}/quarantine}"

mkdir -p "$INCOMING_DIR" "$PROCESSED_DIR" "$QUARANTINE_DIR"

DT="${SMOKE_DT:-$(date -u +%F)}"
SOURCE="${SOURCE:-file}"
TOPIC="${KAFKA_TOPIC:-ingest.file.v1}"

FILE_NAME="smoke_day3_${DT}_$RANDOM.csv"
FILE_PATH="${INCOMING_DIR}/${FILE_NAME}"

# Small deterministic CSV content
cat > "$FILE_PATH" <<CSV
id,name,created_at
1,smoke-${DT},${DT}T00:00:00Z
CSV

SHA=$(sha256_of_file "$FILE_PATH")
RAW_KEY="source=${SOURCE}/dt=${DT}/${SHA}/${FILE_NAME}"

ok "Prepared input file: ${FILE_PATH}"
ok "Computed sha256: ${SHA}"
ok "Expected RAW key: ${RAW_KEY}"

# Clean any leftovers (same filename)
rm -f "${PROCESSED_DIR:?}/${FILE_NAME}" || true
rm -rf "${QUARANTINE_DIR:?}/${FILE_NAME%.csv}" || true

printf "\n== Running ingestor-file (Docker) ==\n"
# We mount our smoke folders to keep the test self-contained.
# NOTE: the service 'ingestor-file' must exist in docker-compose.yml under profile 'manual'.
docker compose --profile manual run --rm \
  -e "SOURCE=${SOURCE}" \
  -e "PROCESSED_DIR=/processed" \
  -e "QUARANTINE_DIR=/quarantine" \
  -e "KAFKA_TOPIC=${TOPIC}" \
  -v "$(pwd)/${INCOMING_DIR}:/incoming" \
  -v "$(pwd)/${PROCESSED_DIR}:/processed" \
  -v "$(pwd)/${QUARANTINE_DIR}:/quarantine" \
  ingestor-file \
  --input "/incoming/${FILE_NAME}" \
  --dt "${DT}"

# Validate filesystem move
if [[ -f "${PROCESSED_DIR}/${FILE_NAME}" ]]; then
  ok "File moved to processed: ${PROCESSED_DIR}/${FILE_NAME}"
else
  if [[ -d "${QUARANTINE_DIR}/${FILE_NAME%.csv}" ]]; then
    warn "File moved to quarantine"
    if [[ -f "${QUARANTINE_DIR}/${FILE_NAME%.csv}/reason.txt" ]]; then
      warn "Quarantine reason:"
      sed -n '1,200p' "${QUARANTINE_DIR}/${FILE_NAME%.csv}/reason.txt" || true
    fi
  fi
  fail "Expected processed file not found: ${PROCESSED_DIR}/${FILE_NAME}"
fi

# Validate MinIO object exists
run_check "MinIO object exists: s3://${MINIO_BUCKET_RAW}/${RAW_KEY}" minio_object_exists "${MINIO_BUCKET_RAW}" "${RAW_KEY}"

# Validate Kafka event exists
run_check "Kafka topic contains message for sha256" kafka_topic_contains_sha "${TOPIC}" "${SHA}"

printf "\nAll Day 3 smoke checks passed.\n"
