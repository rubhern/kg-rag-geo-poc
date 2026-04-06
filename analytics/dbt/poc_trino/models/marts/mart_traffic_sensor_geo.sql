{{ config(
    materialized='table',
    on_table_exists='drop',
    properties={ "format": "'PARQUET'" }
) }}

select
    t.ingest_dt,
    t.sensor_id,
    t.city,
    s.region_id,
    r.region_name,
    s.longitude,
    s.latitude,
    s.geom_wkt as sensor_geom_wkt,
    r.geom_wkt as region_geom_wkt,
    t.reading_id,
    t.vehicle_count,
    t.avg_speed_kmh,
    t.occupancy_pct,
    t.congestion_level_rank,
    t.incident_flag
from {{ ref('stg_traffic') }} t
         join {{ ref('stg_sensor_locations') }} s
              on t.sensor_id = s.sensor_id
                  and t.city = s.city
         join {{ ref('stg_regions') }} r
              on s.region_id = r.region_id