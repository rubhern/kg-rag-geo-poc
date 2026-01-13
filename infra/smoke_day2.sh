#!/usr/bin/env bash
set -euo pipefail

# Day 2 smoke checks: Day 1 + bootstrap validations (extensions, schemas, buckets).
# Run from the repo root (same folder where docker-compose.yml and .env live).

# shellcheck disable=SC1091
source "smoke_common.sh"

require_cmd docker
require_cmd curl
load_dotenv

run_check "docker compose ps" docker_compose_ps
run_check "PostgreSQL reachable (SELECT 1)" pg_select_1
run_check "PostgreSQL extensions (postgis, pgcrypto, vector)" pg_extensions
run_check "PostgreSQL schemas (raw, curated)" pg_schemas

run_check "Kafka reachable (list topics)" kafka_reachable
run_check "MinIO live endpoint" minio_live

# Buckets: raw is required; curated is optional (checked if MINIO_BUCKET_CURATED is set).
run_check "MinIO bucket exists: ${MINIO_BUCKET_RAW}" minio_bucket_exists "${MINIO_BUCKET_RAW}"

if [[ -n "${MINIO_BUCKET_CURATED:-}" ]]; then
  run_check "MinIO bucket exists: ${MINIO_BUCKET_CURATED}" minio_bucket_exists "${MINIO_BUCKET_CURATED}"
else
  warn "MINIO_BUCKET_CURATED is not set; skipping curated bucket check"
fi

printf "\nAll Day 2 smoke checks passed.\n"
