{{ config(materialized='view') }}

with src as (
  select
    reading_id,
    sensor_id,
    road,
    direction,
    road_segment_id,
    city,
    lat,
    lon,
    measured_at_utc,
    vehicle_count,
    avg_speed_kmh,
    occupancy_pct,
    congestion_level,
    incident_flag,
    source_system,
    regexp_extract("$path", 'dt=(\\d{4}-\\d{2}-\\d{2})', 1) as ingest_dt
  from {{ source('raw_s3', 'traffic_csv') }}
)

select
    reading_id,
    sensor_id,
    road,
    direction,
    road_segment_id,
    city,

    try_cast(lat as double) as lat,
    try_cast(lon as double) as lon,

    measured_at_utc as measured_at_utc_raw,
    try(from_iso8601_timestamp(measured_at_utc)) as measured_at_ts,

    try_cast(vehicle_count as integer) as vehicle_count,
    try_cast(avg_speed_kmh as double) as avg_speed_kmh,
    try_cast(occupancy_pct as double) as occupancy_pct,
    upper(trim(congestion_level)) as congestion_level,

    case upper(trim(congestion_level))
        when 'LOW' then 1
        when 'MEDIUM' then 2
        else null
        end as congestion_level_rank,
    upper(trim(incident_flag)) as incident_flag,

    source_system,
    ingest_dt
from src
