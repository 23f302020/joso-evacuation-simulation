"""Check raw constructor observations; no branch is proved without native rows."""
import math
import re
from xml.etree import ElementTree


def integer(text):
    if not isinstance(text, str) or not re.fullmatch(r'-?(?:0|[1-9]\d*)', text):
        raise ValueError('Expected native integer representation')
    return int(text)


def parse(raw):
    matches = list(re.finditer(rb'<jdrtLatGuard\b[^<>\r\n]*/>', raw))
    if not matches or len(matches) != raw.count(b'<jdrtLatGuard'):
        raise ValueError('Missing, incomplete or interleaved native trace')
    rows = []
    for index, match in enumerate(matches, 1):
        try:
            row = dict(ElementTree.fromstring(match.group()).attrib)
        except ElementTree.ParseError as error:
            raise ValueError('Malformed native trace') from error
        if integer(row.get('seq')) != index:
            raise ValueError('Native trace sequence missing or repeated')
        rows.append(row)
    return rows


def derive(row, unspecified, random, walking_type):
    if not all(math.isfinite(v) for v in (unspecified, random)) or unspecified == random:
        raise ValueError('Distinct finite source-bound lateral sentinels required')
    used = set()

    def text(key):
        used.add(key)
        if key not in row or not isinstance(row[key], str) or not row[key]:
            raise ValueError('Missing native field: ' + key)
        return row[key]

    def number(key):
        value = float(text(key))
        if not math.isfinite(value):
            raise ValueError('Nonfinite native field: ' + key)
        return value

    def int_value(key):
        return integer(text(key))

    def boolean(key):
        value = text(key)
        if value not in ('0', '1'):
            raise ValueError('Invalid native Boolean: ' + key)
        return value == '1'

    def equals(actual, expected):
        if actual != expected:
            raise ValueError('Native guard/identity claim differs from raw fields')

    sequence, sim_step = int_value('seq'), int_value('sim_step')
    person, edge, lane = text('person'), text('current_edge'), text('new_lane')
    normal, legacy = boolean('current_edge_normal'), boolean('legacy')
    pos, direction, input_lat = number('new_pos'), int_value('new_dir'), number('input_lat')
    is_unspecified, is_random = boolean('input_unspecified'), boolean('input_random')
    equals(is_unspecified, input_lat == unspecified)
    equals(is_random, input_lat == random)
    stages, remaining, departed = int_value('stages'), int_value('remaining'), int_value('new_departed')
    if sequence < 1 or not 0 <= remaining <= stages:
        raise ValueError('Invalid sequence or stage accounting')
    logged_inherited, final_lat = boolean('inherited'), number('final_lat')
    equals(int_value('final_dir'), direction)
    inherited = False
    old_lat = None
    if is_unspecified and not legacy and normal and stages > remaining:
        equals(boolean('prior_evaluated'), True)
        if int_value('prior_type') == walking_type:
            prior_null = boolean('prior_edge_null')
            prior_edge = None if prior_null else text('prior_edge')
            edge_same = boolean('edge_same')
            equals(edge_same, prior_edge == edge)
            if edge_same:
                arrived, time_same = int_value('prior_arrived'), boolean('time_same')
                equals(time_same, arrived == departed)
                if time_same:
                    equals(boolean('state_evaluated'), True)
                    if not boolean('state_null'):
                        if boolean('person_same'):
                            equals(text('prior_person'), person)
                            lane_null = boolean('old_lane_null')
                            old_lane = None if lane_null else text('old_lane')
                            lane_same = boolean('lane_same')
                            equals(lane_same, old_lane == lane)
                            if lane_same:
                                old_pos, position_same = number('old_pos'), boolean('position_same')
                                equals(position_same, old_pos == pos)
                                if position_same:
                                    old_lat = number('old_lat')
                                    inherited = True
    equals(logged_inherited, inherited)
    if inherited:
        equals(final_lat, old_lat)
    if used != set(row):
        raise ValueError('Unexpected or unevaluated native fields: ' + repr(sorted(set(row) - used)))
    branch = ('inherit' if inherited else 'legacy' if legacy else 'default' if is_unspecified
              else 'random' if is_random else 'explicit')
    return {'sequence': sequence, 'native_sim_step': sim_step, 'person': person,
            'branch': branch, 'inherited': inherited,
            'final_raw_lateral': final_lat, 'new_route_direction': direction}
