# Smoke checks (Day 1)

Goal: fast feedback that the platform is up and bootstrap ran.

## Checks
- Broker reachable (Kafka/Redpanda)
- Object storage reachable (MinIO/S3-compatible)
- PostgreSQL reachable
- (Optional) Grafana reachable
- (Optional) OTEL collector reachable

## Suggested commands (examples)
Replace placeholders with your actual container/service names and ports.

- PostgreSQL:
  - `psql -h localhost -p <PG_PORT> -U <USER> -d <DB> -c "SELECT 1;"`
- Object storage:
  - `curl -sSf http://localhost:<MINIO_PORT>/minio/health/live`
- Broker:
  - `rpk cluster info` (Redpanda) or `kcat -L -b localhost:<KAFKA_PORT>`
- Grafana:
  - `curl -sSf http://localhost:<GRAFANA_PORT>/api/health`

## Expected outcome
All commands return success. If one fails:
- check `docker compose ps`
- inspect logs: `docker compose logs <service>`
- verify healthchecks and `depends_on` ordering
