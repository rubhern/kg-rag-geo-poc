# Smoke checks

These scripts provide fast feedback that the local POC platform is running and bootstrapped.

## Files
- `smoke_day1.sh`: reachability checks (Postgres, Kafka, MinIO, optional Grafana)
- `smoke_day2.sh`: day1 + bootstrap checks (Postgres extensions/schemas, MinIO buckets)
- `smoke_day3.sh`: day2 + end-to-end run-once ingestion (MinIO RAW upload + Kafka publish + processed/quarantine move)
- `smoke_day4.sh`: day3 + end-to-end HTTP ingestion (WireMock 200 → MinIO RAW + Kafka `ingest.http.v1`)
- `smoke_day5.sh`: day2 + end-to-end stream ingestion (Kafka source → MinIO RAW + Kafka `ingest.stream.v1`)
- `smoke_common.sh`: shared helpers

## Run
From the repo infra path (where `docker-compose.yml` and `.env` live):

```bash
chmod +x *.sh
./smoke_day1.sh
./smoke_day2.sh
./smoke_day3.sh
./smoke_day4.sh
./smoke_day5.sh
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
./smoke_day4.sh
./smoke_day5.sh
```

If you don't use `.env`, export variables before running (at least: `POSTGRES_DB/USER`, `MINIO_PORT`, `GRAFANA_PORT`, `MINIO_ROOT_USER/PASSWORD`, `MINIO_BUCKET_RAW`).

## Day 4 prerequisites
- The `mock-api` (WireMock) service must exist in `docker-compose.yml` and be reachable.
- The `ingestor-http` service must exist in `docker-compose.yml` under the `manual` profile.
- MinIO, Kafka and `minio-init` should be up (`docker compose up -d`) before running the smoke checks.

## Day 4 behavior
`smoke_day4.sh` will:
1) Call the mock API endpoint (expects HTTP 200)
2) Run the run-once `ingestor-http` container:
   - Stores the raw payload in MinIO RAW and prints a `raw_uri`
   - Publishes an `ingest.http` event to Kafka topic `ingest.http.v1`
3) Assert:
   - Object exists in MinIO (checked via `mc stat` in `minio-init`)
   - A Kafka message containing the `raw_uri` exists in the topic

## Day 5 prerequisites
- The `ingestor-stream-consumer` service must exist in `docker-compose.yml` (always-on).
- The `ingestor-stream-producer` service must exist in `docker-compose.yml` under the `manual` profile.
- MinIO, Kafka and `minio-init` should be up (`docker compose up -d`) before running the smoke checks.

## Day 5 behavior
`smoke_day5.sh` will:
1) Ensure the stream consumer is running (`docker compose up -d ingestor-stream-consumer`)
2) Run the producer in burst mode (Docker) to publish N messages into `source.posts.v1`
3) Extract the latest `raw_uri` from the consumer logs (the producer does not know storage URIs)
4) Assert:
   - The corresponding object exists in MinIO RAW (checked via `mc stat` in `minio-init`)

## Useful overrides (Day 5)
You can control the burst size/rate and container name:

```bash
PRODUCER_TOTAL=50 PRODUCER_RATE=50 CONSUMER_CONTAINER=poc-ingestor-stream-consumer ./smoke_day5.sh
```
