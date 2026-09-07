"""Scenario C foundation: car owners drive and non-owners walk.

This module only prepares an exclusive person-mode ledger and a private-car
assignment table. It does not create pedestrian routes or run SUMO. Existing
Scenario A/B artifacts are read-only inputs and are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
DEFAULT_REGION_DIR = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
DEFAULT_OUTPUT_DIR = DEFAULT_REGION_DIR / "experiments" / "scenario_c" / "foundation"
DEFAULT_OWNERSHIP_SENSITIVITY_OUTPUT_DIR = (
    DEFAULT_REGION_DIR
    / "experiments"
    / "scenario_c"
    / "inputs"
    / "ownership_sensitivity_20260826"
)
DEFAULT_OWNERSHIP_SCENARIOS = (
    PROGRAM_DIR / "data" / "scenario_c" / "ownership_sensitivity_20260826.csv"
)
DEFAULT_POPULATION_MESH = (
    PROGRAM_DIR
    / "data"
    / "population_mesh"
    / "5歳階級別人口250メッシュ_茨城"
    / "tblT001178Q08.txt"
)
ELDERLY_COLUMNS = [
    "T001178043",
    "T001178046",
    "T001178049",
    "T001178052",
    "T001178055",
]

TYPE_SPECS = {
    "type1": {
        "column": "type1_car_non_elderly_pop",
        "age_group": "non_elderly",
        "car_ownership": "owner",
        "assigned_mode": "car",
    },
    "type2": {
        "column": "type2_car_elderly_pop",
        "age_group": "elderly",
        "car_ownership": "owner",
        "assigned_mode": "car",
    },
    "type3": {
        "column": "type3_no_car_non_elderly_pop",
        "age_group": "non_elderly",
        "car_ownership": "non_owner",
        "assigned_mode": "walk",
    },
    "type4": {
        "column": "type4_no_car_elderly_pop",
        "age_group": "elderly",
        "car_ownership": "non_owner",
        "assigned_mode": "walk",
    },
}

LEDGER_FIELDS = [
    "person_id",
    "origin_id",
    "KEY_CODE",
    "person_type",
    "age_group",
    "car_ownership",
    "assigned_mode",
    "scenario",
    "ownership_scenario_id",
    "ownership_role",
]

OWNERSHIP_SCENARIO_FIELDS = [
    "scenario_id",
    "non_car_rate",
    "role",
    "source_status",
    "source_note",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_nonnegative_integer(value: Any, field: str, origin_id: str) -> int:
    number = float(value or 0)
    if number < 0 or not number.is_integer():
        raise ValueError(f"{origin_id}: {field} must be a non-negative integer: {value}")
    return int(number)


def read_optional_integer(value: Any, field: str, key_code: str) -> int | None:
    text = str(value or "").strip()
    if not text or text == "*":
        return None
    number = float(text)
    if number < 0 or not number.is_integer():
        raise ValueError(f"{key_code}: {field} must be a non-negative integer: {value}")
    return int(number)


def allocate_bounded_proportional(
    weights: list[int], target_total: int, upper_bounds: list[int]
) -> list[int]:
    """Allocate an integer total proportionally while respecting cell bounds."""
    if len(weights) != len(upper_bounds):
        raise ValueError("weights and upper_bounds must have the same length")
    if any(value < 0 for value in [*weights, *upper_bounds]):
        raise ValueError("weights and upper_bounds must be non-negative")
    if target_total < 0 or target_total > sum(upper_bounds):
        raise ValueError("target_total exceeds allocation bounds")
    if target_total == 0:
        return [0] * len(weights)
    weight_total = sum(weights)
    if weight_total <= 0:
        raise ValueError("positive target_total requires positive weights")

    quotas = [weight / weight_total * target_total for weight in weights]
    counts = [
        min(bound, math.floor(quota))
        for quota, bound in zip(quotas, upper_bounds)
    ]
    remainder = target_total - sum(counts)
    order = sorted(
        range(len(weights)),
        key=lambda index: (
            quotas[index] - counts[index],
            upper_bounds[index] - counts[index],
            -index,
        ),
        reverse=True,
    )
    while remainder:
        progressed = False
        for index in order:
            if counts[index] < upper_bounds[index]:
                counts[index] += 1
                remainder -= 1
                progressed = True
                if remainder == 0:
                    break
        if not progressed:
            raise ValueError("bounded proportional allocation cannot satisfy target")
    return counts


def round_half_up(value: float) -> int:
    """Round a non-negative count target without Python's ties-to-even rule."""
    if value < 0:
        raise ValueError("round_half_up only accepts non-negative values")
    return math.floor(value + 0.5)


def read_ownership_scenarios(path: Path) -> list[dict[str, Any]]:
    """Read validated Scenario C ownership sensitivity definitions."""
    rows = read_csv_rows(path)
    if not rows:
        raise ValueError("at least one ownership scenario is required")
    scenarios: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    reference_count = 0
    for row in rows:
        missing = [field for field in OWNERSHIP_SCENARIO_FIELDS if field not in row]
        if missing:
            raise ValueError(f"ownership scenario fields are missing: {missing}")
        scenario_id = str(row["scenario_id"]).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", scenario_id):
            raise ValueError(f"invalid ownership scenario_id: {scenario_id}")
        if scenario_id in seen_ids:
            raise ValueError(f"duplicate ownership scenario_id: {scenario_id}")
        seen_ids.add(scenario_id)
        non_car_rate = float(row["non_car_rate"])
        if not 0 <= non_car_rate <= 1:
            raise ValueError(f"{scenario_id}: non_car_rate is outside [0, 1]")
        role = str(row["role"]).strip()
        reference_count += role == "reference_assumption"
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "non_car_rate": non_car_rate,
                "role": role,
                "source_status": str(row["source_status"]).strip(),
                "source_note": str(row["source_note"]).strip(),
            }
        )
    if reference_count != 1:
        raise ValueError("ownership scenarios require exactly one reference_assumption")
    return scenarios


def build_elderly_population_map(
    population_mesh_path: Path,
) -> tuple[dict[str, int], dict[str, Any]]:
    """Distribute confidentiality-aggregated elderly counts before area selection."""
    source_rows = read_csv_rows_with_encoding(population_mesh_path, "cp932")
    mesh_rows = {
        str(row.get("KEY_CODE", "")).zfill(10): row
        for row in source_rows
        if str(row.get("KEY_CODE", "")).strip()
    }
    elderly_by_mesh: dict[str, int] = {}
    grouped_members: set[str] = set()
    group_diagnostics: list[dict[str, Any]] = []

    for key_code, row in sorted(mesh_rows.items()):
        if str(row.get("HTKSYORI", "")).strip() != "1":
            continue
        members = [
            value.strip().zfill(10)
            for value in str(row.get("GASSAN", "")).split(";")
            if value.strip()
        ]
        if not members:
            continue
        group_keys = [key_code, *members]
        missing = [value for value in group_keys if value not in mesh_rows]
        if missing:
            raise ValueError(f"{key_code}: missing confidentiality group rows: {missing}")
        totals = [
            read_nonnegative_integer(
                mesh_rows[value].get("T001178001"), "T001178001", value
            )
            for value in group_keys
        ]
        elderly_total = sum(
            read_optional_integer(row.get(column), column, key_code) or 0
            for column in ELDERLY_COLUMNS
        )
        allocations = allocate_bounded_proportional(totals, elderly_total, totals)
        for value, allocation in zip(group_keys, allocations):
            if value in grouped_members:
                raise ValueError(f"{value}: appears in multiple confidentiality groups")
            elderly_by_mesh[value] = allocation
            grouped_members.add(value)
        group_diagnostics.append(
            {
                "representative_key": key_code,
                "member_keys": group_keys,
                "group_population": sum(totals),
                "group_elderly": elderly_total,
                "allocations": dict(zip(group_keys, allocations)),
            }
        )

    for key_code, row in mesh_rows.items():
        if key_code in grouped_members:
            continue
        if str(row.get("HTKSYORI", "")).strip() == "2":
            raise ValueError(f"{key_code}: confidentiality source has no resolved representative")
        elderly_by_mesh[key_code] = sum(
            read_optional_integer(row.get(column), column, key_code) or 0
            for column in ELDERLY_COLUMNS
        )

    return elderly_by_mesh, {
        "method": "confidentiality_group_population_proportional_largest_remainder",
        "group_count": len(group_diagnostics),
        "groups": group_diagnostics,
    }


def read_csv_rows_with_encoding(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open(encoding=encoding, newline="") as handle:
        return list(csv.DictReader(handle))


def build_scenario_c_agent_types(
    *,
    population_mesh_path: Path,
    agent_origins_path: Path,
    ownership_source_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create closing Scenario C Type counts with corrected elderly populations."""
    elderly_by_mesh, age_diagnostics = build_elderly_population_map(population_mesh_path)
    ownership_rows = {
        str(row["KEY_CODE"]).zfill(10): row
        for row in read_csv_rows(ownership_source_path)
    }
    rows: list[dict[str, Any]] = []
    for origin in sorted(read_csv_rows(agent_origins_path), key=lambda row: row["origin_id"]):
        key_code = str(origin["KEY_CODE"]).zfill(10)
        if key_code not in elderly_by_mesh:
            raise ValueError(f"{key_code}: elderly population is unavailable")
        if key_code not in ownership_rows:
            raise ValueError(f"{key_code}: ownership rate is unavailable")
        total_pop = read_nonnegative_integer(
            origin.get("total_pop"), "total_pop", origin["origin_id"]
        )
        elderly_pop = elderly_by_mesh[key_code]
        if elderly_pop > total_pop:
            raise ValueError(
                f"{key_code}: corrected elderly_pop {elderly_pop} exceeds total_pop {total_pop}"
            )
        non_car_rate = float(ownership_rows[key_code].get("non_car_rate") or 0)
        if not 0 <= non_car_rate <= 1:
            raise ValueError(f"{key_code}: non_car_rate is outside [0, 1]")

        non_elderly_pop = total_pop - elderly_pop
        type4 = round(elderly_pop * non_car_rate)
        type2 = elderly_pop - type4
        type3 = round(non_elderly_pop * non_car_rate)
        type1 = non_elderly_pop - type3
        rows.append(
            {
                "origin_id": origin["origin_id"],
                "KEY_CODE": key_code,
                "lon": origin.get("lon", ""),
                "lat": origin.get("lat", ""),
                "total_pop": total_pop,
                "elderly_pop": elderly_pop,
                "non_elderly_pop": non_elderly_pop,
                "non_car_rate": non_car_rate,
                "type1_car_non_elderly_pop": type1,
                "type2_car_elderly_pop": type2,
                "type3_no_car_non_elderly_pop": type3,
                "type4_no_car_elderly_pop": type4,
                "age_allocation_method": age_diagnostics["method"],
                "ownership_status": "provisional_existing_non_car_rate",
            }
        )

    declared_population = sum(row["total_pop"] for row in rows)
    declared_elderly = sum(row["elderly_pop"] for row in rows)
    type_population = sum(
        row["type1_car_non_elderly_pop"]
        + row["type2_car_elderly_pop"]
        + row["type3_no_car_non_elderly_pop"]
        + row["type4_no_car_elderly_pop"]
        for row in rows
    )
    if type_population != declared_population:
        raise AssertionError("Scenario C Type counts do not preserve population")
    selected_keys = {str(row["KEY_CODE"]).zfill(10) for row in rows}
    selected_groups = [
        group
        for group in age_diagnostics["groups"]
        if selected_keys.intersection(group["member_keys"])
    ]
    selected_age_diagnostics = {
        "method": age_diagnostics["method"],
        "source_group_count": age_diagnostics["group_count"],
        "selected_group_count": len(selected_groups),
        "groups": selected_groups,
    }

    return rows, {
        "origin_count": len(rows),
        "declared_population": declared_population,
        "declared_elderly": declared_elderly,
        "type_population": type_population,
        "car_people": sum(
            row["type1_car_non_elderly_pop"] + row["type2_car_elderly_pop"]
            for row in rows
        ),
        "walk_people": sum(
            row["type3_no_car_non_elderly_pop"] + row["type4_no_car_elderly_pop"]
            for row in rows
        ),
        "ownership_status": "provisional_existing_non_car_rate",
        "age_allocation": selected_age_diagnostics,
    }


def build_scenario_c_agent_types_for_rate(
    *,
    population_mesh_path: Path,
    agent_origins_path: Path,
    scenario: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Allocate one citywide non-car rate while preserving exact integer totals."""
    elderly_by_mesh, age_diagnostics = build_elderly_population_map(population_mesh_path)
    components: list[dict[str, Any]] = []
    for origin in sorted(read_csv_rows(agent_origins_path), key=lambda row: row["origin_id"]):
        key_code = str(origin["KEY_CODE"]).zfill(10)
        if key_code not in elderly_by_mesh:
            raise ValueError(f"{key_code}: elderly population is unavailable")
        total_pop = read_nonnegative_integer(
            origin.get("total_pop"), "total_pop", origin["origin_id"]
        )
        elderly_pop = elderly_by_mesh[key_code]
        if elderly_pop > total_pop:
            raise ValueError(
                f"{key_code}: corrected elderly_pop {elderly_pop} exceeds total_pop {total_pop}"
            )
        components.append(
            {
                "origin_id": origin["origin_id"],
                "KEY_CODE": key_code,
                "lon": origin.get("lon", ""),
                "lat": origin.get("lat", ""),
                "total_pop": total_pop,
                "elderly_pop": elderly_pop,
                "non_elderly_pop": total_pop - elderly_pop,
            }
        )

    rate = float(scenario["non_car_rate"])
    total_population = sum(row["total_pop"] for row in components)
    total_elderly = sum(row["elderly_pop"] for row in components)
    total_non_elderly = total_population - total_elderly
    target_walk_people = round_half_up(total_population * rate)
    target_walk_elderly = round_half_up(total_elderly * rate)
    target_walk_non_elderly = target_walk_people - target_walk_elderly
    if not 0 <= target_walk_non_elderly <= total_non_elderly:
        raise ValueError("non-elderly walk target is outside population bounds")

    walk_elderly = allocate_bounded_proportional(
        [row["elderly_pop"] for row in components],
        target_walk_elderly,
        [row["elderly_pop"] for row in components],
    )
    walk_non_elderly = allocate_bounded_proportional(
        [row["non_elderly_pop"] for row in components],
        target_walk_non_elderly,
        [row["non_elderly_pop"] for row in components],
    )

    rows: list[dict[str, Any]] = []
    for component, type4, type3 in zip(
        components, walk_elderly, walk_non_elderly
    ):
        rows.append(
            {
                **component,
                "non_car_rate": rate,
                "type1_car_non_elderly_pop": component["non_elderly_pop"] - type3,
                "type2_car_elderly_pop": component["elderly_pop"] - type4,
                "type3_no_car_non_elderly_pop": type3,
                "type4_no_car_elderly_pop": type4,
                "age_allocation_method": age_diagnostics["method"],
                "ownership_allocation_method": (
                    "city_target_age_inner_total_then_mesh_"
                    "population_proportional_largest_remainder"
                ),
                "ownership_scenario_id": scenario["scenario_id"],
                "ownership_role": scenario["role"],
                "ownership_status": scenario["source_status"],
                "ownership_source_note": scenario["source_note"],
            }
        )

    walk_people = sum(
        row["type3_no_car_non_elderly_pop"] + row["type4_no_car_elderly_pop"]
        for row in rows
    )
    walk_elderly_people = sum(row["type4_no_car_elderly_pop"] for row in rows)
    type_population = sum(
        row["type1_car_non_elderly_pop"]
        + row["type2_car_elderly_pop"]
        + row["type3_no_car_non_elderly_pop"]
        + row["type4_no_car_elderly_pop"]
        for row in rows
    )
    if type_population != total_population or walk_people != target_walk_people:
        raise AssertionError("formal Scenario C ownership allocation does not close")
    if walk_elderly_people != target_walk_elderly:
        raise AssertionError("formal Scenario C elderly allocation does not close")

    selected_keys = {row["KEY_CODE"] for row in rows}
    selected_groups = [
        group
        for group in age_diagnostics["groups"]
        if selected_keys.intersection(group["member_keys"])
    ]
    return rows, {
        "scenario_id": scenario["scenario_id"],
        "role": scenario["role"],
        "source_status": scenario["source_status"],
        "non_car_rate": rate,
        "origin_count": len(rows),
        "declared_population": total_population,
        "declared_elderly": total_elderly,
        "type_population": type_population,
        "car_people": total_population - walk_people,
        "walk_people": walk_people,
        "walk_elderly_people": walk_elderly_people,
        "walk_non_elderly_people": walk_people - walk_elderly_people,
        "target_walk_people": target_walk_people,
        "target_walk_elderly": target_walk_elderly,
        "target_walk_non_elderly": target_walk_non_elderly,
        "mode_overlap_count": 0,
        "unassigned_count": 0,
        "allocation_method": (
            "city_target_age_inner_total_then_mesh_"
            "population_proportional_largest_remainder"
        ),
        "age_allocation": {
            "method": age_diagnostics["method"],
            "source_group_count": age_diagnostics["group_count"],
            "selected_group_count": len(selected_groups),
            "groups": selected_groups,
        },
    }


def validate_mode_ledger(rows: list[dict[str, Any]]) -> dict[str, int]:
    person_ids = [str(row["person_id"]) for row in rows]
    if len(person_ids) != len(set(person_ids)):
        raise AssertionError("duplicate Scenario C person_id")

    expected = {
        "type1": ("owner", "car", "non_elderly"),
        "type2": ("owner", "car", "elderly"),
        "type3": ("non_owner", "walk", "non_elderly"),
        "type4": ("non_owner", "walk", "elderly"),
    }
    for row in rows:
        person_type = str(row["person_type"])
        if person_type not in expected:
            raise AssertionError(f"invalid Scenario C person_type: {person_type}")
        ownership, mode, age_group = expected[person_type]
        if (
            row["car_ownership"] != ownership
            or row["assigned_mode"] != mode
            or row["age_group"] != age_group
            or row["scenario"] != "C"
        ):
            raise AssertionError(f"invalid Scenario C mode assignment: {row['person_id']}")

    car_people = sum(row["assigned_mode"] == "car" for row in rows)
    walk_people = sum(row["assigned_mode"] == "walk" for row in rows)
    elderly_people = sum(row["age_group"] == "elderly" for row in rows)
    return {
        "person_count": len(rows),
        "unique_person_count": len(set(person_ids)),
        "car_people": car_people,
        "walk_people": walk_people,
        "elderly_people": elderly_people,
        "mode_overlap_count": 0,
        "unassigned_count": 0,
    }


def build_mode_ledger(agent_types_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build an exclusive all-person Scenario C ledger.

    The function intentionally rejects non-closing Type totals. Allocation and
    rounding policy must be fixed upstream instead of being silently repaired.
    """
    rows: list[dict[str, Any]] = []
    declared_population = 0
    declared_elderly = 0
    for source in sorted(read_csv_rows(agent_types_path), key=lambda row: row["origin_id"]):
        origin_id = source["origin_id"]
        total_pop = read_nonnegative_integer(source.get("total_pop"), "total_pop", origin_id)
        elderly_pop = read_nonnegative_integer(
            source.get("elderly_pop"), "elderly_pop", origin_id
        )
        counts = {
            person_type: read_nonnegative_integer(
                source.get(spec["column"]), spec["column"], origin_id
            )
            for person_type, spec in TYPE_SPECS.items()
        }
        if sum(counts.values()) != total_pop:
            raise ValueError(
                f"{origin_id}: Type1-4 total {sum(counts.values())} "
                f"does not match total_pop {total_pop}"
            )
        if counts["type2"] + counts["type4"] != elderly_pop:
            raise ValueError(
                f"{origin_id}: elderly Type total "
                f"{counts['type2'] + counts['type4']} does not match elderly_pop {elderly_pop}"
            )

        declared_population += total_pop
        declared_elderly += elderly_pop
        for person_type, spec in TYPE_SPECS.items():
            for index in range(1, counts[person_type] + 1):
                rows.append(
                    {
                        "person_id": f"{origin_id}_{person_type}_{index:04d}",
                        "origin_id": origin_id,
                        "KEY_CODE": source.get("KEY_CODE", ""),
                        "person_type": person_type,
                        "age_group": spec["age_group"],
                        "car_ownership": spec["car_ownership"],
                        "assigned_mode": spec["assigned_mode"],
                        "scenario": "C",
                        "ownership_scenario_id": source.get(
                            "ownership_scenario_id", ""
                        ),
                        "ownership_role": source.get("ownership_role", ""),
                    }
                )

    diagnostics = validate_mode_ledger(rows)
    if diagnostics["person_count"] != declared_population:
        raise AssertionError("Scenario C ledger does not preserve declared population")
    if diagnostics["elderly_people"] != declared_elderly:
        raise AssertionError("Scenario C ledger does not preserve declared elderly population")
    diagnostics["declared_population"] = declared_population
    diagnostics["declared_elderly"] = declared_elderly
    return rows, diagnostics


def build_ownership_sensitivity_suite(
    *,
    population_mesh_path: Path,
    agent_origins_path: Path,
    ownership_scenarios_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write formal Scenario C population ledgers without routes or SUMO runs."""
    if "scenario_c" not in {part.lower() for part in output_dir.parts}:
        raise ValueError("Scenario C output directory must contain a scenario_c path segment")
    scenarios = read_ownership_scenarios(ownership_scenarios_path)
    prepared: list[tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]] = []
    for scenario in scenarios:
        agent_rows, diagnostics = build_scenario_c_agent_types_for_rate(
            population_mesh_path=population_mesh_path,
            agent_origins_path=agent_origins_path,
            scenario=scenario,
        )
        prepared.append((scenario, agent_rows, diagnostics))

    source_hashes = {
        str(population_mesh_path): sha256(population_mesh_path),
        str(agent_origins_path): sha256(agent_origins_path),
        str(ownership_scenarios_path): sha256(ownership_scenarios_path),
    }
    suite_entries: list[dict[str, Any]] = []
    for scenario, agent_rows, diagnostics in prepared:
        scenario_dir = output_dir / scenario["scenario_id"]
        agent_types_path = scenario_dir / "scenario_c_agent_types.csv"
        ledger_path = scenario_dir / "scenario_c_mode_ledger.csv"
        manifest_path = scenario_dir / "manifest.json"
        write_csv(agent_types_path, list(agent_rows[0].keys()), agent_rows)
        ledger_rows, ledger_diagnostics = build_mode_ledger(agent_types_path)
        write_csv(ledger_path, LEDGER_FIELDS, ledger_rows)
        if ledger_diagnostics["walk_people"] != diagnostics["walk_people"]:
            raise AssertionError("Scenario C sensitivity ledger walk total mismatch")
        manifest = {
            "scenario": "C",
            "ownership_scenario": scenario,
            "status": "formal_population_allocation_only_not_runnable",
            "description": "car owners drive; non-owners walk; no rescue cars; no buses",
            "car_route_implemented": False,
            "pedestrian_routes_implemented": False,
            "sumo_run_authorized": False,
            "diagnostics": {**diagnostics, **ledger_diagnostics},
            "sources": source_hashes,
            "outputs": {
                "scenario_c_agent_types": str(agent_types_path),
                "scenario_c_mode_ledger": str(ledger_path),
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        suite_entries.append(
            {
                "scenario_id": scenario["scenario_id"],
                "role": scenario["role"],
                "non_car_rate": scenario["non_car_rate"],
                "walk_people": diagnostics["walk_people"],
                "car_people": diagnostics["car_people"],
                "manifest": str(manifest_path),
            }
        )

    suite_manifest = {
        "scenario": "C",
        "status": "formal_population_allocation_only_not_runnable",
        "sumo_run_authorized": False,
        "scenario_count": len(suite_entries),
        "sources": source_hashes,
        "ownership_scenarios": suite_entries,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(suite_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return suite_manifest


def select_private_vehicle_assignments(
    scenario_a_assignments_path: Path,
) -> list[dict[str, str]]:
    """Copy only private cars into Scenario C; rescue cars and buses are excluded."""
    source_rows = read_csv_rows(scenario_a_assignments_path)
    rows = [dict(row) for row in source_rows if row.get("vehicle_kind") == "private_car"]
    vehicle_ids = [row.get("vehicle_id", "") for row in rows]
    if not rows:
        raise ValueError("Scenario C requires at least one private_car assignment")
    if "" in vehicle_ids or len(vehicle_ids) != len(set(vehicle_ids)):
        raise ValueError("Scenario C private vehicle IDs must be non-empty and unique")
    if any(row.get("vehicle_kind") != "private_car" for row in rows):
        raise AssertionError("Scenario C vehicle assignments contain a non-private vehicle")
    return rows


def build_foundation(
    *,
    agent_types_path: Path,
    scenario_a_assignments_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write validated Scenario C foundation artifacts to an isolated directory."""
    if "scenario_c" not in {part.lower() for part in output_dir.parts}:
        raise ValueError("Scenario C output directory must contain a scenario_c path segment")

    ledger_rows, diagnostics = build_mode_ledger(agent_types_path)
    vehicle_rows = select_private_vehicle_assignments(scenario_a_assignments_path)
    assignment_fields = list(vehicle_rows[0].keys())

    ledger_path = output_dir / "scenario_c_mode_ledger.csv"
    assignments_path = output_dir / "scenario_c_private_vehicle_assignments.csv"
    manifest_path = output_dir / "manifest.json"
    write_csv(ledger_path, LEDGER_FIELDS, ledger_rows)
    write_csv(assignments_path, assignment_fields, vehicle_rows)

    manifest = {
        "scenario": "C",
        "status": "foundation_only_not_runnable",
        "description": "car owners drive; non-owners walk; no rescue cars; no buses",
        "pedestrian_routes_implemented": False,
        "sumo_run_authorized": False,
        "diagnostics": {
            **diagnostics,
            "private_vehicle_count": len(vehicle_rows),
            "rescue_vehicle_count": 0,
            "bus_vehicle_count": 0,
        },
        "sources": {
            str(agent_types_path): sha256(agent_types_path),
            str(scenario_a_assignments_path): sha256(scenario_a_assignments_path),
        },
        "outputs": {
            "mode_ledger": str(ledger_path),
            "private_vehicle_assignments": str(assignments_path),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def prepare_foundation(
    *,
    population_mesh_path: Path,
    agent_origins_path: Path,
    ownership_source_path: Path,
    scenario_a_assignments_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Prepare corrected Scenario C Type input and validated foundation outputs."""
    agent_rows, agent_diagnostics = build_scenario_c_agent_types(
        population_mesh_path=population_mesh_path,
        agent_origins_path=agent_origins_path,
        ownership_source_path=ownership_source_path,
    )
    agent_types_path = output_dir / "scenario_c_agent_types.csv"
    agent_fields = list(agent_rows[0].keys())
    write_csv(agent_types_path, agent_fields, agent_rows)
    manifest = build_foundation(
        agent_types_path=agent_types_path,
        scenario_a_assignments_path=scenario_a_assignments_path,
        output_dir=output_dir,
    )
    manifest["agent_type_diagnostics"] = agent_diagnostics
    manifest["sources"].update(
        {
            str(population_mesh_path): sha256(population_mesh_path),
            str(agent_origins_path): sha256(agent_origins_path),
            str(ownership_source_path): sha256(ownership_source_path),
        }
    )
    manifest["outputs"]["scenario_c_agent_types"] = str(agent_types_path)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["foundation", "prepare", "formalize-ownership"]
    )
    parser.add_argument(
        "--agent-types",
        type=Path,
        default=DEFAULT_REGION_DIR / "derived" / "agent_types.csv",
    )
    parser.add_argument("--population-mesh", type=Path, default=DEFAULT_POPULATION_MESH)
    parser.add_argument(
        "--agent-origins",
        type=Path,
        default=DEFAULT_REGION_DIR / "derived" / "agent_origins_10pct.csv",
    )
    parser.add_argument(
        "--ownership-source",
        type=Path,
        default=DEFAULT_REGION_DIR / "derived" / "agent_types.csv",
    )
    parser.add_argument(
        "--ownership-scenarios",
        type=Path,
        default=DEFAULT_OWNERSHIP_SCENARIOS,
    )
    parser.add_argument(
        "--scenario-a-assignments",
        type=Path,
        default=DEFAULT_REGION_DIR / "derived" / "scenario_a_vehicle_assignments.csv",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--sensitivity-output-dir",
        type=Path,
        default=DEFAULT_OWNERSHIP_SENSITIVITY_OUTPUT_DIR,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "foundation":
        manifest = build_foundation(
            agent_types_path=args.agent_types,
            scenario_a_assignments_path=args.scenario_a_assignments,
            output_dir=args.output_dir,
        )
    elif args.command == "prepare":
        manifest = prepare_foundation(
            population_mesh_path=args.population_mesh,
            agent_origins_path=args.agent_origins,
            ownership_source_path=args.ownership_source,
            scenario_a_assignments_path=args.scenario_a_assignments,
            output_dir=args.output_dir,
        )
    elif args.command == "formalize-ownership":
        manifest = build_ownership_sensitivity_suite(
            population_mesh_path=args.population_mesh,
            agent_origins_path=args.agent_origins,
            ownership_scenarios_path=args.ownership_scenarios,
            output_dir=args.sensitivity_output_dir,
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
