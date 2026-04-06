{{ config(materialized='table') }}

select distinct
    trim(region_id) as region_id,
    trim(region_name) as region_name,
    trim(city) as city,
    trim(region_type) as region_type,
    cast(srid as integer) as srid,
    trim(geom_wkt) as geom_wkt,
    trim(source) as source
from {{ ref('stg_regions') }}
where region_id is not null
  and region_name is not null
  and geom_wkt is not null
  and cast(srid as integer) = 4326