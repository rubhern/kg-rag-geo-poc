# Smoke checks

These scripts provide fast feedback that the local POC platform is running and bootstrapped.

## Files
- `smoke_day1.sh`: reachability checks (Postgres, Kafka, MinIO, optional Grafana)
- `smoke_day2.sh`: day1 + bootstrap checks (Postgres extensions/schemas, MinIO buckets)
- `smoke_common.sh`: shared helpers

## Run
From the repo infra path (where `docker-compose.yml` and `.env` live):

```bash
chmod +x *.sh
./smoke_day1.sh
./smoke_day2.sh
```

If you don't use `.env`, export variables before running (at least: POSTGRES_DB/USER, MINIO_PORT, GRAFANA_PORT, MINIO_ROOT_USER/PASSWORD, MINIO_BUCKET_RAW).
