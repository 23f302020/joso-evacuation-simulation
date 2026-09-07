"""Read the frozen Joso City inputs without modifying legacy artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .domain import (
    DRTRequest,
    DRTVehicle,
    Evacuee,
    EvacueeStatus,
    RequestStatus,
    TransportMode,
)
from .workspace import JOSO_CITY_CODE

DEFAULT_PARAMETERS_PATH = Path("04_プログラム/config/jdrt_parameters_v1.json")
DEFAULT_SOURCES_PATH = Path("04_プログラム/config/jdrt_input_sources_v1.json")


@dataclass(frozen=True)
class ShelterInput:
    shelter_id: str
    name: str
    edge_id: str
    capacity: int | None
    active_from_sec: int
    active_until_sec: int


@dataclass(frozen=True)
class PrivateVehicleInput:
    vehicle_id: str
    origin_id: str
    from_edge: str
    shelter_id: str
    to_edge: str
    depart_sec: int
    passenger_equivalent: float


@dataclass(frozen=True)
class DRTRequestPlan:
    request: DRTRequest
    shelter_id: str
    shelter_edge: str


@dataclass(frozen=True)
class TrueClosureTimeline:
    """True World closure data for the controller, never for dispatch scoring."""

    closure_time_by_edge: Mapping[str, int]
    time_step_count: int


@dataclass(frozen=True)
class JDRTInputBundle:
    city_code: str
    evacuees: tuple[Evacuee, ...]
    request_plans: tuple[DRTRequestPlan, ...]
    vehicles: tuple[DRTVehicle, ...]
    shelters: tuple[ShelterInput, ...]
    private_vehicles: tuple[PrivateVehicleInput, ...]
    true_closures: TrueClosureTimeline
    parameters: Mapping[str, Any]
    input_sha256_by_role: Mapping[str, str]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_input_sources(
    project_root: Path,
    sources_path: Path | None = None,
) -> dict[str, Path]:
    """Verify every frozen input and return paths indexed by source role."""

    root = project_root.resolve()
    manifest_path = (root / (sources_path or DEFAULT_SOURCES_PATH)).resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("city_code") != JOSO_CITY_CODE:
        raise ValueError("input source manifest must be for Joso City 08211")

    paths: dict[str, Path] = {}
    for item in manifest.get("files", []):
        role = str(item["role"])
        path = (root / str(item["path"])).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"missing JDRT input for {role}: {path}")
        actual_hash = _sha256(path)
        expected_hash = str(item["sha256"])
        if actual_hash != expected_hash:
            raise ValueError(
                f"SHA-256 mismatch for {role}: {actual_hash} != {expected_hash}"
            )
        if "expected_rows" in item:
            actual_rows = len(_read_csv(path))
            if actual_rows != int(item["expected_rows"]):
                raise ValueError(
                    f"row count mismatch for {role}: "
                    f"{actual_rows} != {item['expected_rows']}"
                )
        if role in paths:
            raise ValueError(f"duplicate input source role: {role}")
        paths[role] = path
    return paths


def _make_evacuees(
    row: Mapping[str, str],
    request_time_sec: int,
    scores: Mapping[str, float],
) -> dict[str, list[Evacuee]]:
    origin_id = row["origin_id"]
    type4_count = int(row["type4_no_car_elderly_pop"])
    type3_total = int(row["type3_no_car_non_elderly_pop"])
    type3_mobility_count = int(row["type3_mobility_limited_candidate_pop"])
    if type3_mobility_count > type3_total:
        raise ValueError(f"mobility-limited Type3 exceeds Type3 total: {origin_id}")

    categories: dict[str, list[Evacuee]] = {
        "type4": [],
        "type3_mobility_limited": [],
        "type3": [],
    }
    definitions = (
        ("type4", type4_count, 4, "elderly"),
        ("type3_mobility_limited", type3_mobility_count, 3, "non_elderly"),
        ("type3", type3_total - type3_mobility_count, 3, "non_elderly"),
    )
    for category, count, person_type, age_group in definitions:
        for index in range(1, count + 1):
            categories[category].append(
                Evacuee(
                    person_id=f"{origin_id}_{category}_{index:04d}",
                    origin_id=origin_id,
                    person_type=person_type,
                    age_group=age_group,
                    has_private_car=False,
                    vulnerability_score=float(scores[category]),
                    ready_time=request_time_sec,
                    eligible_for_drt=True,
                    transport_mode=TransportMode.DRT,
                    status=EvacueeStatus.WAITING,
                    request_time=request_time_sec,
                )
            )
    return categories


def _balanced_groups(
    categories: Mapping[str, list[Evacuee]],
    group_count: int,
) -> list[list[Evacuee]]:
    groups: list[list[Evacuee]] = [[] for _ in range(group_count)]
    for category in ("type4", "type3_mobility_limited", "type3"):
        for person in categories[category]:
            target = min(range(group_count), key=lambda index: (len(groups[index]), index))
            groups[target].append(person)
    return groups


def _load_people_and_requests(
    agent_rows: list[dict[str, str]],
    rescue_rows: list[dict[str, str]],
    parameters: Mapping[str, Any],
) -> tuple[tuple[Evacuee, ...], tuple[DRTRequestPlan, ...]]:
    rescue_by_origin = {row["origin_id"]: row for row in rescue_rows}
    population = parameters["population"]
    request_time = int(population["request_time_sec"])
    scores = population["vulnerability_scores"]
    capacity_reference = int(population["request_grouping"]["capacity_reference"])

    evacuees: list[Evacuee] = []
    plans: list[DRTRequestPlan] = []
    for agent_row in sorted(agent_rows, key=lambda row: row["origin_id"]):
        origin_id = agent_row["origin_id"]
        if origin_id not in rescue_by_origin:
            raise ValueError(f"origin missing from rescue_od.csv: {origin_id}")
        rescue_row = rescue_by_origin[origin_id]
        categories = _make_evacuees(agent_row, request_time, scores)
        people = [person for group in categories.values() for person in group]
        if not people:
            continue
        legacy_rescue_count = int(rescue_row["rescue_vehicle_count"])
        group_count = min(
            len(people),
            max(1, legacy_rescue_count, math.ceil(len(people) / capacity_reference)),
        )
        groups = _balanced_groups(categories, group_count)
        for group_index, group in enumerate(groups, start=1):
            request_id = f"request_{origin_id}_{group_index:04d}"
            request = DRTRequest(
                request_id=request_id,
                person_ids=tuple(person.person_id for person in group),
                origin_edge=agent_row["sumo_edge_id"],
                request_time=request_time,
                vulnerability=sum(person.vulnerability_score for person in group)
                / len(group),
                status=RequestStatus.WAITING,
            )
            plans.append(
                DRTRequestPlan(
                    request=request,
                    shelter_id=rescue_row["shelter_id"],
                    shelter_edge=rescue_row["shelter_edge_id"],
                )
            )
        evacuees.extend(people)
    return tuple(evacuees), tuple(plans)


def _load_vehicles(
    rows: list[dict[str, str]], parameters: Mapping[str, Any]
) -> tuple[DRTVehicle, ...]:
    fleet = parameters["fleet"]
    vehicles = []
    for row in sorted(rows, key=lambda item: item["bus_id"]):
        is_welfare = row["bus_vtype"] == "bus_welfare"
        capacity = int(
            fleet["welfare_capacity"] if is_welfare else fleet["standard_capacity"]
        )
        vehicles.append(
            DRTVehicle(
                vehicle_id=row["bus_id"],
                capacity=capacity,
                current_edge=row["pickup_edge"],
            )
        )
    return tuple(vehicles)


def _load_shelters(
    rows: list[dict[str, str]], parameters: Mapping[str, Any]
) -> tuple[ShelterInput, ...]:
    shelter_parameters = parameters["shelters"]
    shelters = []
    for row in sorted(rows, key=lambda item: item["shelter_id"]):
        if row["is_safe_destination"].lower() != "true":
            continue
        raw_capacity = int(row["capacity"])
        shelters.append(
            ShelterInput(
                shelter_id=row["shelter_id"],
                name=row["name"],
                edge_id=row["sumo_edge_id"],
                capacity=None if raw_capacity == 0 else raw_capacity,
                active_from_sec=int(shelter_parameters["active_from_sec"]),
                active_until_sec=int(shelter_parameters["active_until_sec"]),
            )
        )
    return tuple(shelters)


def _load_private_vehicles(
    rows: list[dict[str, str]],
) -> tuple[PrivateVehicleInput, ...]:
    return tuple(
        PrivateVehicleInput(
            vehicle_id=row["vehicle_id"],
            origin_id=row["origin_id"],
            from_edge=row["from_sumo_edge_id"],
            shelter_id=row["shelter_id"],
            to_edge=row["to_sumo_edge_id"],
            depart_sec=int(float(row["depart"])),
            passenger_equivalent=float(row["passenger_equivalent"]),
        )
        for row in rows
        if row["vehicle_kind"] == "private_car"
    )


def _load_true_closures(data: Mapping[str, Any]) -> TrueClosureTimeline:
    metadata = data.get("metadata", {})
    if metadata.get("city_code") != JOSO_CITY_CODE:
        raise ValueError("closure timeline must be for Joso City 08211")
    events = data.get("closures", [])
    closure_time_by_edge: dict[str, int] = {}
    for event in events:
        sim_time = int(event["sim_time_sec"])
        for edge_id in event["closed_sumo_edge_ids"]:
            closure_time_by_edge.setdefault(str(edge_id), sim_time)
    return TrueClosureTimeline(
        closure_time_by_edge=closure_time_by_edge,
        time_step_count=len(events),
    )


def load_joso_input_bundle(
    project_root: Path,
    parameters_path: Path | None = None,
    sources_path: Path | None = None,
) -> JDRTInputBundle:
    """Load and validate the formally frozen Joso City JDRT inputs."""

    root = project_root.resolve()
    parameter_file = (root / (parameters_path or DEFAULT_PARAMETERS_PATH)).resolve()
    parameters = _read_json(parameter_file)
    if parameters.get("city_code") != JOSO_CITY_CODE:
        raise ValueError("JDRT parameters must be for Joso City 08211")
    paths = verify_input_sources(root, sources_path)

    agent_rows = _read_csv(paths["population_and_types"])
    rescue_rows = _read_csv(paths["rescue_substitution_and_fixed_shelter"])
    evacuees, request_plans = _load_people_and_requests(
        agent_rows, rescue_rows, parameters
    )
    vehicles = _load_vehicles(
        _read_csv(paths["drt_initial_vehicle_edges"]), parameters
    )
    shelters = _load_shelters(_read_csv(paths["safe_shelters"]), parameters)
    private_vehicles = _load_private_vehicles(
        _read_csv(paths["private_vehicle_demand"])
    )
    true_closures = _load_true_closures(_read_json(paths["true_closure_timeline"]))

    expected = parameters["population"]
    if len(evacuees) != int(expected["drt_eligible"]):
        raise ValueError("DRT eligible population does not match Parameter Registry")
    if len(request_plans) != int(expected["request_grouping"]["expected_request_count"]):
        raise ValueError("request count does not match Parameter Registry")
    if len(vehicles) != int(parameters["fleet"]["total"]):
        raise ValueError("fleet size does not match Parameter Registry")
    if len(shelters) != int(parameters["shelters"]["expected_count"]):
        raise ValueError("shelter count does not match Parameter Registry")
    if len(private_vehicles) != int(parameters["traffic_demand"]["private_vehicle_count"]):
        raise ValueError("private vehicle count does not match Parameter Registry")

    source_manifest = _read_json(
        (root / (sources_path or DEFAULT_SOURCES_PATH)).resolve()
    )
    hashes = {str(item["role"]): str(item["sha256"]) for item in source_manifest["files"]}
    return JDRTInputBundle(
        city_code=JOSO_CITY_CODE,
        evacuees=evacuees,
        request_plans=request_plans,
        vehicles=vehicles,
        shelters=shelters,
        private_vehicles=private_vehicles,
        true_closures=true_closures,
        parameters=parameters,
        input_sha256_by_role=hashes,
    )
