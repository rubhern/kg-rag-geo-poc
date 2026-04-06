{{ config(materialized='view') }}

with src as (
  select
      sensor_id,
      city,
      region_id,
      longitude,
      latitude,
      srid,
      geom_wkt,
      source
  from {{ source('raw_s3', 'raw_sensor_locations') }}
)

select trim(sensor_id)           as sensor_id,
       trim(city)                as city,
       trim(region_id)           as region_id,
       cast(longitude as double) as longitude,
       cast(latitude as double)  as latitude,
       cast(srid as integer)     as srid,
       trim(geom_wkt)            as geom_wkt,
       trim(source)              as source
from raw_sensor_locations
