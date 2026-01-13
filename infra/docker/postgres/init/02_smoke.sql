SELECT 'postgis'  AS ext, extversion FROM pg_extension WHERE extname='postgis';
SELECT 'pgcrypto' AS ext, extversion FROM pg_extension WHERE extname='pgcrypto';
SELECT 'vector'   AS ext, extversion FROM pg_extension WHERE extname='vector';
