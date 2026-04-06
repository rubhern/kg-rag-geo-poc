import csv
import json
from shapely import wkt
from shapely.geometry import mapping

input_csv = "regions_export.csv"
output_geojson = "regions.geojson"

features = []

with open(input_csv, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        geom = wkt.loads(row["geom_wkt"])

        properties = {
            "region_id": row["region_id"],
            "region_name": row["region_name"],
            "city": row["city"],
            "region_type": row["region_type"],
            "srid": int(row["srid"]),
            "source": row["source"],
        }

        feature = {
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": properties,
        }

        features.append(feature)

feature_collection = {
    "type": "FeatureCollection",
    "features": features,
}

with open(output_geojson, "w", encoding="utf-8") as f:
    json.dump(feature_collection, f, ensure_ascii=False, indent=2)

print(f"GeoJSON generated: {output_geojson}")
print(f"Features: {len(features)}")