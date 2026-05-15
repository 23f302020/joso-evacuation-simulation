"""Phase 2: SUMO道路ネットワーク変換ユーティリティ。"""

from __future__ import annotations

import argparse
import ast
import csv
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import osmnx as ox
from networkx import MultiDiGraph
from shapely import wkt

from p2_sumo_env import configure_sumo_environment


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

GRAPHML_PATH = PROGRAM_DIR / "output" / "network" / "joso_road_network.graphml"
SUMO_OUTPUT_DIR = PROGRAM_DIR / "output" / "sumo"
SUMO_NETWORK_DIR = SUMO_OUTPUT_DIR / "network"
SUMO_DERIVED_DIR = SUMO_OUTPUT_DIR / "derived"
NETWORK_CITIES_DIR = PROGRAM_DIR / "output" / "network" / "cities"
REGION_SUMO_DIR = SUMO_OUTPUT_DIR / "regions"
REGION_TARGETS_CSV = REGION_SUMO_DIR / "_management" / "phase2_region_targets.csv"

OSM_XML_PATH = SUMO_NETWORK_DIR / "joso.osm.xml"
NET_XML_PATH = SUMO_NETWORK_DIR / "joso.net.xml"
OSM_WAY_MAPPING_CSV = SUMO_DERIVED_DIR / "phase1_edge_osm_way_mapping.csv"
NETCONVERT_LOG_PATH = SUMO_NETWORK_DIR / "netconvert.log"


@dataclass(frozen=True)
class NetworkTarget:
    """SUMOネットワーク変換の入力・出力パス一式。"""

    label: str
    city_code: str
    city_name: str
    graphml_path: Path
    sumo_network_dir: Path
    sumo_derived_dir: Path
    osm_xml_path: Path
    net_xml_path: Path
    osm_way_mapping_csv: Path
    netconvert_log_path: Path


def load_region_targets() -> dict[str, dict[str, str]]:
    if not REGION_TARGETS_CSV.exists():
        return {}

    with REGION_TARGETS_CSV.open(newline="", encoding="utf-8-sig") as f:
        return {row["city_code"]: row for row in csv.DictReader(f)}


def build_default_target() -> NetworkTarget:
    return NetworkTarget(
        label="joso_default",
        city_code="08211",
        city_name="常総市",
        graphml_path=GRAPHML_PATH,
        sumo_network_dir=SUMO_NETWORK_DIR,
        sumo_derived_dir=SUMO_DERIVED_DIR,
        osm_xml_path=OSM_XML_PATH,
        net_xml_path=NET_XML_PATH,
        osm_way_mapping_csv=OSM_WAY_MAPPING_CSV,
        netconvert_log_path=NETCONVERT_LOG_PATH,
    )


def build_region_target(city_code: str) -> NetworkTarget:
    code = city_code.strip()
    targets = load_region_targets()
    if code not in targets:
        raise ValueError(
            f"{code} is not in {REGION_TARGETS_CSV}. "
            "Run p2_region_inventory.py all first, or choose a Phase 2 region target."
        )

    row = targets[code]
    region_dir = REGION_SUMO_DIR / code
    return NetworkTarget(
        label=f"region_{code}",
        city_code=code,
        city_name=row["city_name"],
        graphml_path=NETWORK_CITIES_DIR / code / f"{code}_road_network.graphml",
        sumo_network_dir=region_dir / "network",
        sumo_derived_dir=region_dir / "derived",
        osm_xml_path=region_dir / "network" / f"{code}.osm.xml",
        net_xml_path=region_dir / "network" / f"{code}.net.xml",
        osm_way_mapping_csv=region_dir / "derived" / "phase1_edge_osm_way_mapping.csv",
        netconvert_log_path=region_dir / "network" / "netconvert.log",
    )


def build_target(city_code: str | None = None) -> NetworkTarget:
    if city_code:
        return build_region_target(city_code)
    return build_default_target()


def ensure_dirs(target: NetworkTarget) -> None:
    target.sumo_network_dir.mkdir(parents=True, exist_ok=True)
    target.sumo_derived_dir.mkdir(parents=True, exist_ok=True)


def load_graph(target: NetworkTarget) -> MultiDiGraph:
    if not target.graphml_path.exists():
        raise FileNotFoundError(f"GraphML not found: {target.graphml_path}")
    return ox.load_graphml(target.graphml_path)


def parse_list_like(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return [value]
    text = value.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except (SyntaxError, ValueError):
            return [value]
    return [value]


def first_tag_value(value: Any) -> str | None:
    values = [str(v) for v in parse_list_like(value) if v is not None and str(v).strip()]
    return values[0] if values else None


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value).strip().lower()
    return "yes" if text in {"true", "1", "yes"} else "no"


def edge_phase1_id(u: Any, v: Any, key: Any) -> str:
    return f"{u}_{v}_{key}"


def edge_points(graph: MultiDiGraph, u: Any, v: Any, data: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = data.get("geometry")
    if geometry:
        line = wkt.loads(str(geometry))
        return [(float(x), float(y)) for x, y in line.coords]

    u_data = graph.nodes[u]
    v_data = graph.nodes[v]
    return [
        (float(u_data["x"]), float(u_data["y"])),
        (float(v_data["x"]), float(v_data["y"])),
    ]


def add_tag(parent: ET.Element, key: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return
    ET.SubElement(parent, "tag", {"k": key, "v": text})


def inspect_graph(target: NetworkTarget) -> None:
    graph = load_graph(target)
    node_attrs: set[str] = set()
    edge_attrs: set[str] = set()
    for _, data in list(graph.nodes(data=True))[:200]:
        node_attrs.update(data.keys())
    for _, _, _, data in list(graph.edges(keys=True, data=True))[:500]:
        edge_attrs.update(data.keys())

    print(f"target={target.label}")
    print(f"city_code={target.city_code}")
    print(f"city_name={target.city_name}")
    print(f"graphml={target.graphml_path}")
    print(f"directed={graph.is_directed()}")
    print(f"multigraph={graph.is_multigraph()}")
    print(f"nodes={graph.number_of_nodes()}")
    print(f"edges={graph.number_of_edges()}")
    print(f"node_attrs={sorted(node_attrs)}")
    print(f"edge_attrs={sorted(edge_attrs)}")
    print(f"osm_xml={target.osm_xml_path}")
    print(f"net_xml={target.net_xml_path}")


def export_osm(target: NetworkTarget) -> None:
    ensure_dirs(target)
    graph = load_graph(target)

    osm = ET.Element(
        "osm",
        {
            "version": "0.6",
            "generator": f"p2_sumo_network.py:{target.label}",
        },
    )
    node_ids_written: set[str] = set()
    generated_node_id = 9_000_000_000_000

    for node_id, data in graph.nodes(data=True):
        attrs = {
            "id": str(node_id),
            "lat": str(data["y"]),
            "lon": str(data["x"]),
        }
        ET.SubElement(osm, "node", attrs)
        node_ids_written.add(str(node_id))

    mapping_rows: list[dict[str, Any]] = []
    way_records: list[dict[str, Any]] = []
    way_id = 1
    for u, v, key, data in graph.edges(keys=True, data=True):
        phase1_id = edge_phase1_id(u, v, key)
        points = edge_points(graph, u, v, data)

        refs: list[str] = [str(u)]
        for lon, lat in points[1:-1]:
            generated_node_id += 1
            node_ref = str(generated_node_id)
            ET.SubElement(osm, "node", {"id": node_ref, "lat": str(lat), "lon": str(lon)})
            node_ids_written.add(node_ref)
            refs.append(node_ref)
        refs.append(str(v))

        for ref in refs:
            if ref not in node_ids_written:
                raise ValueError(f"OSM node reference was not written: {ref}")

        highway = first_tag_value(data.get("highway")) or "unclassified"
        way_records.append(
            {
                "id": str(way_id),
                "refs": refs,
                "tags": {
                    "highway": highway,
                    "oneway": "yes",
                    "name": first_tag_value(data.get("name")),
                    "ref": first_tag_value(data.get("ref")),
                    "lanes": first_tag_value(data.get("lanes")),
                    "maxspeed": first_tag_value(data.get("maxspeed")),
                    "bridge": first_tag_value(data.get("bridge")),
                    "tunnel": first_tag_value(data.get("tunnel")),
                    "phase1_edge_id": phase1_id,
                    "phase1_u": u,
                    "phase1_v": v,
                    "phase1_key": key,
                    "phase1_osmid": data.get("osmid"),
                },
            }
        )

        mapping_rows.append(
            {
                "phase1_edge_id": phase1_id,
                "u": u,
                "v": v,
                "key": key,
                "osmid": data.get("osmid", ""),
                "phase2_osm_way_id": way_id,
                "highway": highway,
                "oneway": bool_text(data.get("oneway", True)),
                "length": data.get("length", ""),
                "has_geometry": bool(data.get("geometry")),
                "geometry_point_count": len(points),
            }
        )
        way_id += 1

    for record in way_records:
        way = ET.SubElement(osm, "way", {"id": record["id"]})
        for ref in record["refs"]:
            ET.SubElement(way, "nd", {"ref": ref})
        for key, value in record["tags"].items():
            add_tag(way, key, value)

    tree = ET.ElementTree(osm)
    ET.indent(tree, space="  ")
    tree.write(target.osm_xml_path, encoding="utf-8", xml_declaration=True)

    with target.osm_way_mapping_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "phase1_edge_id",
            "u",
            "v",
            "key",
            "osmid",
            "phase2_osm_way_id",
            "highway",
            "oneway",
            "length",
            "has_geometry",
            "geometry_point_count",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mapping_rows)

    print(f"[INFO] saved: {target.osm_xml_path}")
    print(f"[INFO] saved: {target.osm_way_mapping_csv}")
    print(f"[INFO] ways: {len(mapping_rows)}")


def run_netconvert(target: NetworkTarget) -> None:
    ensure_dirs(target)
    configure_sumo_environment()
    if not target.osm_xml_path.exists():
        raise FileNotFoundError(f"OSM XML not found: {target.osm_xml_path}")

    command = [
        "netconvert",
        "--osm-files",
        str(target.osm_xml_path),
        "--output-file",
        str(target.net_xml_path),
        "--geometry.remove",
        "false",
        "--roundabouts.guess",
        "true",
        "--ramps.guess",
        "true",
        "--no-warnings",
        "false",
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    target.netconvert_log_path.write_text(
        "\n".join(
            [
                "$ " + " ".join(command),
                "",
                "[stdout]",
                result.stdout,
                "[stderr]",
                result.stderr,
                f"[returncode] {result.returncode}",
            ]
        ),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"netconvert failed. See {target.netconvert_log_path}")
    print(f"[INFO] saved: {target.net_xml_path}")
    print(f"[INFO] log: {target.netconvert_log_path}")


def list_region_targets() -> None:
    targets = load_region_targets()
    if not targets:
        raise FileNotFoundError(f"Region target CSV not found or empty: {REGION_TARGETS_CSV}")
    for code in sorted(targets):
        row = targets[code]
        print(f"{code}\t{row['city_name']}\t{row['phase2_region_dir']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["inspect", "export-osm", "netconvert", "all", "list-region-targets"],
        help="実行する処理",
    )
    parser.add_argument(
        "--city-code",
        help="Phase 2全域拡張対象の市区町村コード。省略時は従来の常総市単独出力を使う。",
    )
    args = parser.parse_args()

    if args.command == "list-region-targets":
        list_region_targets()
        return

    target = build_target(args.city_code)
    if args.command == "inspect":
        inspect_graph(target)
    elif args.command == "export-osm":
        export_osm(target)
    elif args.command == "netconvert":
        run_netconvert(target)
    elif args.command == "all":
        inspect_graph(target)
        export_osm(target)
        run_netconvert(target)


if __name__ == "__main__":
    main()
