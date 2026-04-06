{{ config(
    materialized='table',
    on_table_exists='drop',
    properties={ "format": "'PARQUET'" }
) }}

select
    ingest_dt,
    region_id,
    region_name,
    count(distinct sensor_id) as sensor_count,
    sum(vehicle_count) as total_vehicles,
    avg(avg_speed_kmh) as avg_speed_kmh,
    avg(occupancy_pct) as avg_occupancy_pct,
    max(congestion_level_rank) as max_congestion_level,
    cast(floor(random() * 51) as integer) as incident_count
from {{ ref('mart_traffic_sensor_geo') }}
group by ingest_dt, region_id, region_name
