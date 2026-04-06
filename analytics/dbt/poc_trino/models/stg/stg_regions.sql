{{ config(materialized='view') }}

with src as (
  select
      region_id,
      region_name,
      region_type,
      city,
      srid,
      geom_wkt,
      source
  from {{ source('raw_s3', 'raw_regions') }}
)

select
    trim(region_id) as region_id,
    trim(region_name) as region_name,
    trim(region_type) as region_type,
    trim(city) as city,
    cast(srid as integer) as srid,
    trim(geom_wkt) as geom_wkt,
    trim(source) as source
from raw_regions
