{{ config(
    materialized='table',
    on_table_exists='drop',
    properties={ "format": "'PARQUET'" }
) }}

select
    date(coalesce(measured_at_ts, from_iso8601_timestamp(ingest_dt || 'T00:00:00Z'))) as traffic_date,
    sensor_id,
    city,
    count(*) as readings,
    sum(vehicle_count) as vehicles_total,
    avg(avg_speed_kmh) as avg_speed_kmh_avg,
    avg(occupancy_pct) as occupancy_pct_avg,
    max(congestion_level) as congestion_level_max,
    sum(case incident_flag when 'Y' then 1 else 0 end) as incidents
from {{ ref('stg_traffic') }}
group by 1,2,3
