# Smoke checks

These scripts provide fast feedback that the local POC platform is running and bootstrapped.

## Files
- `smoke_day1.sh`: reachability checks (Postgres, Kafka, MinIO, optional Grafana)
- `smoke_day2.sh`: day1 + bootstrap checks (Postgres extensions/schemas, MinIO buckets)
- `smoke_day3.sh`: day2 + end-to-end run-once ingestion (MinIO RAW upload + Kafka publish + processed/quarantine move)
- `smoke_common.sh`: shared helpers

## Run
From the repo infra path (where `docker-compose.yml` and `.env` live):

```bash
chmod +x *.sh
./smoke_day1.sh
./smoke_day2.sh
./smoke_day3.sh
```

## Day 3 prerequisites
- The `ingestor-file` service must exist in `docker-compose.yml` under the `manual` profile.
- MinIO, Kafka and `minio-init` should be up (`docker compose up -d`) before running the smoke checks.

## Day 3 behavior
`smoke_day3.sh` will:
1) Create a small CSV under a dedicated workspace: `.smoke/day3/incoming/`
2) Run the run-once ingestor container:
   - Uploads the file to MinIO bucket `${MINIO_BUCKET_RAW}` under:
     `source=<source>/dt=<YYYY-MM-DD>/<sha256>/<filename>`
   - Publishes an `ingest.file` event to Kafka topic `ingest.file.v1` (override with `KAFKA_TOPIC`)
   - Moves the input file to `.smoke/day3/processed/` (or `.smoke/day3/quarantine/` on failure)
3) Assert:
   - Object exists in MinIO (checked via `mc stat` in `minio-init`)
   - A Kafka message containing the SHA-256 exists in the topic
   - The file ended in `processed`

## Useful overrides
You can customize the smoke workspace and/or dt:

```bash
SMOKE_ROOT=.smoke/day3 \
SMOKE_DT=2026-01-20 \
KAFKA_TOPIC=ingest.file.v1 \
./smoke_day3.sh
```

If you don't use `.env`, export variables before running (at least: `POSTGRES_DB/USER`, `MINIO_PORT`, `GRAFANA_PORT`, `MINIO_ROOT_USER/PASSWORD`, `MINIO_BUCKET_RAW`).
