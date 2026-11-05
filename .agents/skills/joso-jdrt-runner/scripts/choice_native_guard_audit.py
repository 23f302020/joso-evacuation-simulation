"""Read-only native guard accounting; outputs do not grant research READY."""
import math


def actor_accounting(rows, speeds, step):
    if not rows or not math.isfinite(step) or step <= 0:
        raise ValueError('Nonempty observations and positive finite clock required')
    departed, arrived = set(), set()
    for index, row in enumerate(rows, 1):
        if row['time_sec'] != index * step or row['teleports'] or row['collisions']:
            raise ValueError('Missing clock step, teleport or collision')
        new, done = row['departed'], row['arrived']
        if (len(new) != len(set(new)) or len(done) != len(set(done))
                or departed.intersection(new) or arrived.intersection(done)):
            raise ValueError('Repeated departure or arrival')
        departed.update(new)
        arrived.update(done)
        if not arrived <= departed or set(row['actors']) != departed - arrived:
            raise ValueError('Whole-person accounting differs')
        for person, actor in row['actors'].items():
            values = [actor['lane_position_m'], actor['speed_mps'], *actor['xy']]
            if (person not in speeds or not all(math.isfinite(v) for v in values)
                    or not 0 <= actor['speed_mps'] <= speeds[person]):
                raise ValueError('Unknown person, nonfinite getter or native speed outside bound')
    if not departed <= set(speeds):
        raise ValueError('Unregistered synthetic person departed')
    return {'steps': len(rows), 'departed': sorted(departed), 'arrived': sorted(arrived),
            'active_final': sorted(departed - arrived)}


def position_receipts(operations, exact_target):
    for op in operations:
        if op.get('api_error') or set(op['before']) != set(op['after']):
            raise ValueError('API rejection or changed person set during replacement')
        person = op['person']
        if person not in op['before']:
            raise ValueError('Replacement target is not present')
        for other, before in op['before'].items():
            after = op['after'][other]
            if other != person and before != after:
                raise ValueError('Replacement changed a non-target actor')
            if other == person and exact_target:
                for key in ('edge_id', 'lane_id', 'lane_position_m', 'xy'):
                    if before[key] != after[key]:
                        raise ValueError('Instantaneous replacement position differs')


def next_directions(operations, rows):
    directions = {}
    for op in operations:
        if op['purpose'] != 'new_route':
            continue
        person = op['person']
        start = op['after'][person]
        endpoint_delta = op['requested_arrival_pos_m'] - start['lane_position_m']
        if endpoint_delta == 0:
            raise ValueError('No new-route directional endpoint')
        expected = 1 if endpoint_delta > 0 else -1
        for row in rows:
            actor = row['actors'].get(person)
            if row['time_sec'] <= op['time_sec'] or actor is None:
                continue
            if actor['lane_id'] != start['lane_id']:
                raise ValueError('Direction probe left its lane before a nonzero observed step')
            distance = actor['lane_position_m'] - start['lane_position_m']
            if distance != 0:
                if (1 if distance > 0 else -1) != expected:
                    raise ValueError('Next nonzero native movement opposes the new route')
                directions[person] = expected
                break
        else:
            raise ValueError('No next nonzero movement observed')
    return directions


def link_operations(operations, trace_rows, native_units_per_second):
    if not math.isfinite(native_units_per_second) or native_units_per_second <= 0:
        raise ValueError('Positive source-bound native clock unit required')
    indices = []
    for op in operations:
        before, after = op['trace_count_before'], op['trace_count_after']
        if type(before) is not int or after != before + 1 or not 0 <= before < len(trace_rows):
            raise ValueError('Operation did not emit exactly one identified constructor row')
        trace = trace_rows[before]
        if (trace['person'] != op['person']
                or int(trace['sim_step']) != op['time_sec'] * native_units_per_second
                or before in indices):
            raise ValueError('Native person/clock/constructor ordinal differs')
        indices.append(before)
    return indices
