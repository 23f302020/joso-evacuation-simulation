"""Nonadoptable passenger interval candidate; not imported by the frozen stack.

Callers must bind native rows/routes/net and route-reset/arrival receipts. This
pure prototype neither runs SUMO nor writes/reclassifies research artifacts.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import math


def require(value, reason):
    if not value:
        raise ValueError(reason)


def passenger_links(net):
    """Map every reachable internal lane to external (source,target) pairs."""
    lanes = {lane.attrib['id']: (edge.attrib['id'], lane.attrib)
             for edge in net.findall('edge') for lane in edge.findall('lane')}
    connections = [dict(c.attrib) for c in net.findall('connection')]
    outgoing = defaultdict(list)
    for c in connections:
        outgoing[c['from'] + '_' + c['fromLane']].append(c)

    def allowed(lane):
        require(lane in lanes, 'Unknown connection lane')
        a = lanes[lane][1]
        return ('passenger' in a.get('allow', 'passenger').split()
                and 'passenger' not in a.get('disallow', '').split())

    result = defaultdict(set)
    for c in connections:
        if c['from'].startswith(':') or c['to'].startswith(':') or not c.get('via'):
            continue
        if not (allowed(c['from'] + '_' + c['fromLane']) and allowed(c['to'] + '_' + c['toLane'])):
            continue
        pending, visited = deque([c['via']]), set()
        while pending:
            lane = pending.popleft()
            if lane in visited:
                continue
            visited.add(lane)
            require(lane in lanes and lanes[lane][0].startswith(':'), 'Unknown internal via lane')
            require(allowed(lane), 'Passenger connection uses a prohibited internal lane')
            result[lane].add((c['from'], c['to']))
            for next_link in outgoing[lane]:
                if next_link['to'] == c['to'] and next_link.get('via'):
                    pending.append(next_link['via'])
    return dict(result)


@dataclass(frozen=True)
class Anchor:
    time: float
    index: int
    version: int


def advance_index(anchor, route, index, now, version, closures):
    """An explicit route reset supplies a new anchor; no inferred version reset."""
    require(math.isfinite(now) and now >= 0 and 0 <= index < len(route), 'Invalid observation clock/index')
    if anchor is None:
        require(index == 0, 'Skipped initial edges require an explicit creation anchor')
        return Anchor(now, index, version), []
    require(anchor.version == version, 'Route version requires an explicit source-bound reset')
    require(0 <= anchor.index <= index and now >= anchor.time, 'Backward index/clock or invalid anchor')
    rows = []
    for entered_index in range(anchor.index + 1, index + 1):
        edge = route[entered_index]
        closure = closures.get(edge)
        if closure is not None:
            require(math.isfinite(closure) and closure >= 0, 'Invalid closure clock')
        rows.append({'time_lower_sec': anchor.time, 'time_upper_sec': now,
                     'from_edge': route[anchor.index], 'to_edge': edge,
                     'route_index': entered_index,
                     'closed_entry': closure is not None and now >= closure})
    return Anchor(now, index, version), rows


def advance(anchor, frame, route, links, closures):
    require(frame['phase'] == 'after_step_before_control', 'Unsupported observation phase')
    kind = frame['observation_kind']
    if kind in ('departure_pending', 'reentry_pending'):
        return anchor, []
    require(kind in ('onroad', 'parked'), 'Unexplained missing observation')
    edge, lane = frame['road_id'], frame['lane_id']
    index, version = int(frame['route_index']), int(frame['route_version'])
    require(0 <= index < len(route), 'Route index outside route')
    if edge.startswith(':'):
        require(lane.rsplit('_', 1)[0] == edge and lane in links, 'Unknown/mismatched internal lane')
        require(index + 1 < len(route) and (route[index], route[index + 1]) in links[lane],
                'Internal lane not bound to current route occurrence')
    else:
        require(edge == route[index], 'External edge/index mismatch')
    # On an outgoing internal lane, route[index] has already been traversed.
    # Advancing the logical source anchor does not change native movement/state.
    return advance_index(anchor, route, index, float(frame['time_sec']), version, closures)


def arrived(anchor, route, now, version, closures):
    """Requires a separately source-bound actual native arrival receipt."""
    return advance_index(anchor, route, len(route) - 1, now, version, closures)
