from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from jdrt import JOSO_CITY_CODE, load_joso_input_bundle, verify_input_sources


def test_loads_formally_frozen_joso_inputs(program_dir: Path) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)

    assert bundle.city_code == JOSO_CITY_CODE
    assert len(bundle.evacuees) == 3_255
    assert sum(person.person_type == 3 for person in bundle.evacuees) == 2_320
    assert sum(person.person_type == 4 for person in bundle.evacuees) == 935
    assert len(bundle.request_plans) == 1_440
    assert sum(plan.request.party_size for plan in bundle.request_plans) == 3_255
    assert min(plan.request.party_size for plan in bundle.request_plans) == 1
    assert max(plan.request.party_size for plan in bundle.request_plans) == 8
    assert len(bundle.vehicles) == 5
    assert sorted(vehicle.capacity for vehicle in bundle.vehicles) == [4, 8, 8, 8, 8]
    assert len(bundle.shelters) == 9
    assert all(shelter.capacity is None for shelter in bundle.shelters)
    assert len(bundle.private_vehicles) == 8_164
    assert bundle.true_closures.time_step_count == 8
    assert bundle.true_closures.closure_time_by_edge


def test_request_generation_is_deterministic(program_dir: Path) -> None:
    first = load_joso_input_bundle(program_dir.parent)
    second = load_joso_input_bundle(program_dir.parent)

    first_requests = [
        (plan.request.request_id, plan.request.person_ids, plan.shelter_id)
        for plan in first.request_plans
    ]
    second_requests = [
        (plan.request.request_id, plan.request.person_ids, plan.shelter_id)
        for plan in second.request_plans
    ]
    assert first_requests == second_requests


def test_every_drt_person_appears_in_exactly_one_request(program_dir: Path) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)
    assigned = [
        person_id
        for plan in bundle.request_plans
        for person_id in plan.request.person_ids
    ]

    assert len(assigned) == len(set(assigned)) == len(bundle.evacuees)
    assert set(assigned) == {person.person_id for person in bundle.evacuees}


def test_verify_input_sources_rejects_sha_mismatch(tmp_path: Path) -> None:
    data_path = tmp_path / "input.txt"
    data_path.write_text("joso", encoding="utf-8")
    manifest_path = tmp_path / "sources.json"
    manifest_path.write_text(
        json.dumps(
            {
                "city_code": JOSO_CITY_CODE,
                "files": [
                    {
                        "role": "test",
                        "path": "input.txt",
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_input_sources(tmp_path, Path("sources.json"))


def test_verify_input_sources_accepts_matching_sha(tmp_path: Path) -> None:
    data_path = tmp_path / "input.txt"
    data_path.write_text("joso", encoding="utf-8")
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "sources.json"
    manifest_path.write_text(
        json.dumps(
            {
                "city_code": JOSO_CITY_CODE,
                "files": [
                    {"role": "test", "path": "input.txt", "sha256": digest}
                ],
            }
        ),
        encoding="utf-8",
    )

    assert verify_input_sources(tmp_path, Path("sources.json")) == {
        "test": data_path.resolve()
    }
