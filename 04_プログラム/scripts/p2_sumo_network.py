"""Phase 2: SUMO道路ネットワーク変換ユーティリティ。"""

from __future__ import annotations

import argparse
import ast
import csv
import subprocess
import xml.etree.ElementTree as ET
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

OSM_XML_PATH = SUMO_NETWORK_DIR / "joso.osm.xml"
NET_XML_PATH = SUMO_NETWORK_DIR / "joso.net.xml"
OSM_WAY_MAPPING_CSV = SUMO_DERIVED_DIR / "phase1_edge_osm_way_mapping.csv"
NETCONVERT_LOG_PATH = SUMO_NETWORK_DIR / "netconvert.log"


def ensure_dirs() -> None:
    SUMO_NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def load_graph() -> MultiDiGraph:
    return ox.load_graphml(GRAPHML_PATH)


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


def inspect_graph() -> None:
    graph = load_graph()
    node_attrs: set[str] = set()
    edge_attrs: set[str] = set()
    for _, data in list(graph.nodes(data=True))[:200]:
        node_attrs.update(data.keys())
    for _, _, _, data in list(graph.edges(keys=True, data=True))[:500]:
        edge_attrs.update(data.keys())

    print(f"graphml={GRAPHML_PATH}")
    print(f"directed={graph.is_directed()}")
    print(f"multigraph={graph.is_multigraph()}")
    print(f"nodes={graph.number_of_nodes()}")
    print(f"edges={graph.number_of_edges()}")
    print(f"node_attrs={sorted(node_attrs)}")
    print(f"edge_attrs={sorted(edge_attrs)}")


def export_osm() -> None:
    ensure_dirs()
    graph = load_graph()

    osm = ET.Element("osm", {"version": "0.6", "generator": "p2_sumo_network.py"})
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
    tree.write(OSM_XML_PATH, encoding="utf-8", xml_declaration=True)

    with OSM_WAY_MAPPING_CSV.open("w", newline="", encoding="utf-8") as f:
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

    print(f"[INFO] saved: {OSM_XML_PATH}")
    print(f"[INFO] saved: {OSM_WAY_MAPPING_CSV}")
    print(f"[INFO] ways: {len(mapping_rows)}")


def run_netconvert() -> None:
    ensure_dirs()
    configure_sumo_environment()
    if not OSM_XML_PATH.exists():
        raise FileNotFoundError(f"OSM XML not found: {OSM_XML_PATH}")

    command = [
        "netconvert",
        "--osm-files",
        str(OSM_XML_PATH),
        "--output-file",
        str(NET_XML_PATH),
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
    NETCONVERT_LOG_PATH.write_text(
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
        raise RuntimeError(f"netconvert failed. See {NETCONVERT_LOG_PATH}")
    print(f"[INFO] saved: {NET_XML_PATH}")
    print(f"[INFO] log: {NETCONVERT_LOG_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["inspect", "export-osm", "netconvert", "all"],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "inspect":
        inspect_graph()
    elif args.command == "export-osm":
        export_osm()
    elif args.command == "netconvert":
        run_netconvert()
    elif args.command == "all":
        inspect_graph()
        export_osm()
        run_netconvert()


if __name__ == "__main__":
    main()
