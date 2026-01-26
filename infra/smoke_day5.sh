#!/usr/bin/env bash
set -euo pipefail

# Day 5 smoke checks (robust):
# - Kafka reachable
# - MinIO reachable + RAW bucket exists
# - Ensure ingestor-stream consumer is running
# - Run ingestor-stream producer in burst mode (Docker)
# - Extract raw_uri from consumer logs (s3://bucket/key)
# - Validate RAW object exists in MinIO
#
# NOTE:
# Day 4 extracted raw_uri from the ingestor run output.
# Day 5 extracts raw_uri from the *consumer* logs, because the producer doesn't know storage URIs.

# shellcheck disable=SC1091
source "smoke_common.sh"

require_cmd docker
load_dotenv

# MinIO object check (uses minio-init image with mc).
minio_object_exists() {
  local bucket="$1"
  local key="$2"
  docker compose run --rm --entrypoint /bin/sh minio-init -c     "mc alias set local http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}' >/dev/null &&      mc stat local/'${bucket}'/'${key}' >/dev/null"
}

ensure_consumer_up() {
  docker compose up -d ingestor-stream-consumer >/dev/null
}

# --- Checks ---
run_check "docker compose ps" docker_compose_ps
run_check "Kafka reachable (list topics)" kafka_reachable
run_check "MinIO live endpoint" minio_live
run_check "MinIO bucket exists: ${MINIO_BUCKET_RAW}" minio_bucket_exists "${MINIO_BUCKET_RAW}"
run_check "Ensure ingestor-stream consumer is up" ensure_consumer_up

# --- End-to-end run (Docker) ---
TOPIC_SOURCE="${KAFKA_TOPIC_SOURCE:-source.posts.v1}"
PRODUCER_TOTAL="${PRODUCER_TOTAL:-20}"
PRODUCER_RATE="${PRODUCER_RATE:-20}"    # msgs/sec
CONSUMER_CONTAINER="${CONSUMER_CONTAINER:-poc-ingestor-stream-consumer}"

TMP_PRODUCER_OUT="$(mktemp -t smoke_day5_producer.XXXXXX)"
TMP_CONSUMER_OUT="$(mktemp -t smoke_day5_consumer.XXXXXX)"
cleanup() { rm -f "$TMP_PRODUCER_OUT" "$TMP_CONSUMER_OUT"; }
trap cleanup EXIT

printf "\n== Running ingestor-stream producer (Docker) ==\n"
docker compose --profile manual run --rm   -e "KAFKA_TOPIC=${TOPIC_SOURCE}"   -e "POSTS_TOTAL=${PRODUCER_TOTAL}"   -e "POSTS_PER_SEC=${PRODUCER_RATE}"   ingestor-stream-producer 2>&1 | tee "$TMP_PRODUCER_OUT"

# Extract raw_uri from consumer logs (poll a few times to avoid races)
RAW_URI=""
for i in $(seq 1 20); do
  # last minute should be enough for burst + consume
  docker logs "${CONSUMER_CONTAINER}" --since 60s 2>&1 > "$TMP_CONSUMER_OUT" || true
  RAW_URI="$(grep -oE 's3://[^[:space:]"'\'' ]+' "$TMP_CONSUMER_OUT" | tail -n 1 || true)"
  if [[ -n "$RAW_URI" ]]; then
    break
  fi
  sleep 1
done

[[ -n "$RAW_URI" ]] || fail "Could not extract raw_uri from consumer logs. See: ${TMP_CONSUMER_OUT}"

ok "raw_uri: ${RAW_URI}"

# Parse s3://bucket/key (no python required)
BUCKET="$(echo "$RAW_URI" | sed -n 's#^s3://\([^/]*\)/.*#\1#p')"
KEY="$(echo "$RAW_URI" | sed -n 's#^s3://[^/]*/\(.*\)$#\1#p')"

[[ -n "$BUCKET" ]] || fail "Could not parse bucket from raw_uri"
[[ -n "$KEY" ]] || fail "Could not parse key from raw_uri"

run_check "MinIO object exists: ${RAW_URI}" minio_object_exists "${BUCKET}" "${KEY}"

printf "\nAll Day 5 smoke checks passed (RAW validated).\n"
