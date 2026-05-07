"""茨城県境ポリゴンを N03 GML から生成して prefecture_boundary.js に書き出す。"""
import geopandas as gpd
import json
import sys
from pathlib import Path

OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "output" / "unified" / "assets" / "prefecture_boundary.js"
)

CANDIDATES = [
    Path(__file__).resolve().parent.parent
    / "data/admin_boundary/N03-150101_08_GML/N03-20150101_08_GML/N03-15_08_150101.shp",
]

gml = next((p for p in CANDIDATES if p.exists()), None)
if not gml:
    print("ERROR: N03 Shapefile not found", file=sys.stderr)
    sys.exit(1)

print(f"Reading {gml.name} ...", file=sys.stderr)
gdf = gpd.read_file(str(gml))
print(f"  {len(gdf)} features, CRS={gdf.crs}", file=sys.stderr)

gdf["_key"] = 1
pref = gdf.dissolve(by="_key").to_crs("EPSG:4326")
pref["geometry"] = pref["geometry"].simplify(0.002, preserve_topology=True)

geojson = json.loads(pref.to_json())["features"][0]["geometry"]
geojson_str = json.dumps(geojson, ensure_ascii=False, separators=(",", ":"))

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    "window.IBARAKI_BOUNDARY = " + geojson_str + ";\n", encoding="utf-8"
)
print(f"  -> {OUTPUT}  ({len(geojson_str):,} bytes)", file=sys.stderr)
print("Done.", file=sys.stderr)
