"""Exact free-flow lower bounds for branch-and-bound JDRT dispatch."""

from __future__ import annotations

from heapq import heappop, heappush
from math import inf
from pathlib import Path
from xml.etree import ElementTree as ET

from .domain import DRTVehicle
from .input_adapter import DRTRequestPlan


def _allows_bus(attributes: dict[str, str]) -> bool:
    allowed = set(attributes.get("allow", "").split())
    disallowed = set(attributes.get("disallow", "").split())
    if allowed:
        return "bus" in allowed or "all" in allowed
    return "bus" not in disallowed and "all" not in disallowed


class StaticTravelTimeLowerBounds:
    """Read one SUMO net and answer service-time lower bounds efficiently."""

    def __init__(
        self,
        network_path: Path,
        *,
        boarding_time_sec: float,
        bus_max_speed_mps: float = 5.56,
    ) -> None:
        self.network_path = network_path.resolve()
        self.boarding_time_sec = float(boarding_time_sec)
        self.bus_max_speed_mps = float(bus_max_speed_mps)
        if self.boarding_time_sec < 0 or self.bus_max_speed_mps <= 0:
            raise ValueError("routing lower-bound parameters are invalid")

        root = ET.parse(self.network_path).getroot()
        lane_allowed: dict[tuple[str, str], bool] = {}
        self.edge_cost: dict[str, float] = {}
        for edge in root.findall("edge"):
            edge_id = edge.get("id", "")
            if not edge_id or edge_id.startswith(":") or edge.get("function"):
                continue
            lanes = edge.findall("lane")
            bus_lanes = [lane for lane in lanes if _allows_bus(dict(lane.attrib))]
            for lane in lanes:
                lane_allowed[(edge_id, lane.get("index", ""))] = _allows_bus(
                    dict(lane.attrib)
                )
            if not bus_lanes:
                continue
            length = min(float(lane.get("length", "0")) for lane in bus_lanes)
            speed = min(
                self.bus_max_speed_mps,
                max(float(lane.get("speed", "0")) for lane in bus_lanes),
            )
            if length >= 0 and speed > 0:
                self.edge_cost[edge_id] = length / speed

        self.adjacency = {edge_id: [] for edge_id in self.edge_cost}
        self.reverse_adjacency = {edge_id: [] for edge_id in self.edge_cost}
        for connection in root.findall("connection"):
            from_edge = connection.get("from", "")
            to_edge = connection.get("to", "")
            if from_edge not in self.edge_cost or to_edge not in self.edge_cost:
                continue
            if not lane_allowed.get((from_edge, connection.get("fromLane", "")), True):
                continue
            if not lane_allowed.get((to_edge, connection.get("toLane", "")), True):
                continue
            self.adjacency[from_edge].append(to_edge)
            self.reverse_adjacency[to_edge].append(from_edge)

        self._forward_cache: dict[str, dict[str, float]] = {}
        self._to_shelter_cache: dict[str, dict[str, float]] = {}

    def _dijkstra(
        self,
        source: str,
        adjacency: dict[str, list[str]],
    ) -> dict[str, float]:
        if source not in self.edge_cost:
            return {}
        distances = {source: self.edge_cost[source]}
        queue = [(distances[source], source)]
        while queue:
            distance, edge_id = heappop(queue)
            if distance != distances[edge_id]:
                continue
            for next_edge in adjacency[edge_id]:
                next_distance = distance + self.edge_cost[next_edge]
                if next_distance < distances.get(next_edge, inf):
                    distances[next_edge] = next_distance
                    heappush(queue, (next_distance, next_edge))
        return distances

    def from_source(self, source_edge: str) -> dict[str, float]:
        if source_edge not in self._forward_cache:
            self._forward_cache[source_edge] = self._dijkstra(
                source_edge, self.adjacency
            )
        return self._forward_cache[source_edge]

    def to_shelter(self, shelter_edge: str) -> dict[str, float]:
        if shelter_edge not in self._to_shelter_cache:
            self._to_shelter_cache[shelter_edge] = self._dijkstra(
                shelter_edge, self.reverse_adjacency
            )
        return self._to_shelter_cache[shelter_edge]

    def __call__(self, vehicle: DRTVehicle, plan: DRTRequestPlan) -> float:
        pickup = self.from_source(vehicle.current_edge).get(
            plan.request.origin_edge, inf
        )
        shelter = self.to_shelter(plan.shelter_edge).get(
            plan.request.origin_edge, inf
        )
        return pickup + self.boarding_time_sec + shelter
