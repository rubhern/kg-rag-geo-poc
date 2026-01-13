#!/usr/bin/env bash
set -euo pipefail

# Day 1 smoke checks: fast feedback that the platform is up and reachable.
# Run from the repo infra path (same folder where docker-compose.yml and .env live).

# shellcheck disable=SC1091
source "smoke_common.sh"

require_cmd docker
require_cmd curl
load_dotenv

run_check "docker compose ps" docker_compose_ps
run_check "PostgreSQL reachable (SELECT 1)" pg_select_1
run_check "Kafka reachable (list topics)" kafka_reachable
run_check "MinIO live endpoint" minio_live

# Optional checks (comment out if you don't run those services yet)
run_check "Grafana health (optional)" grafana_health_optional || true

printf "\nAll Day 1 smoke checks passed.\n"
