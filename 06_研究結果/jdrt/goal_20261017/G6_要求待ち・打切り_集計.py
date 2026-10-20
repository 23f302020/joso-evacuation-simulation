"""Pure request-analysis component, called only after the all-cell analysis gate.

Cancellation and input rejection are observed competing endpoints, not evidence
of eventual boarding. Only unfinished preboarding wait at H is right-censored.
Origin closure exposure includes boarding, so it is not divided by preboarding wait.
"""
from collections import Counter, defaultdict
import math
from statistics import mean


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def request_summary(requests, people, events, horizon):
    persons = {p['person_id']: p for p in people}
    require(len(persons) == len(people), 'Duplicate people in request analysis')
    requested = {p['person_id'] for p in people if p['selected_jdrt'] == 'True'}
    require(len({q['person_id'] for q in requests}) == len(requests)
            and len({q['request_id'] for q in requests}) == len(requests), 'Duplicate requests')
    require({q['person_id'] for q in requests} == requested, 'Missing or extra selected requests')
    transitions = defaultdict(lambda: defaultdict(list))
    for event in events:
        if event['event'] == 'request_state':
            transitions[event['person_id']][event['after']].append(event)

    def at(row, key):
        require(key in row and row[key] is not None, 'Missing timestamp column: ' + key)
        if row[key] == '':
            return None
        value = float(row[key])
        require(math.isfinite(value) and 0 <= value <= horizon, 'Timestamp outside observed horizon: ' + key)
        return value

    details = []
    fields = ['received_sec', 'accepted_sec', 'boarding_started_sec', 'boarded_sec',
              'alighting_started_sec', 'alighted_sec', 'cancel_sec', 'fallback_sec']
    for q in requests:
        pid = q['person_id']; p = persons[pid]
        require(p['person_type'] in ('type3', 'type4'), 'Unexpected requested person type')
        times = {name: at(q, name) for name in fields}
        received = times['received_sec']
        require(received is not None, 'Request lacks observed receipt time')
        require(all(t is None or t >= received for t in times.values()), 'Stage before receipt')
        started, cancelled = times['boarding_started_sec'], times['cancel_sec']
        status = q['status']
        if started is not None:
            require(cancelled is None and times['fallback_sec'] is None, 'Boarding and cancellation/fallback both present')
            require(started < float(q['deadline_sec']), 'Boarding did not precede deadline')
            require(status in ('served', 'failed_after_boarding', 'time_limit'), 'Invalid postboarding terminal')
            end, kind, censored = started, 'boarding_started', False
        elif cancelled is not None:
            require(status in ('cancelled_timeout', 'cancelled_vehicle_failure'), 'Cancellation status differs')
            end, kind, censored = cancelled, status, False
        elif status == 'rejected_input':
            observations = transitions[pid]['rejected_input']
            require(len(observations) == 1 and observations[0]['request_id'] == q['request_id'], 'Input rejection lacks unique native event')
            end, kind, censored = float(observations[0]['time_sec']), 'rejected_input', False
        elif status == 'time_limit':
            end, kind, censored = horizon, 'horizon_preboarding', True
        else:
            raise RuntimeError('Unresolved request endpoint: ' + status)
        require(received <= end <= horizon, 'Observed wait endpoint outside interval')
        require(q['person_final_status'] == p['status'] and q['person_final_mode'] == p['mode'], 'Request/person final accounting differs')
        if status == 'served':
            require(times['alighted_sec'] is not None, 'Served request lacks completed alighting')
        boarding_observed = None
        boarding_complete = times['boarded_sec'] is not None
        if started is not None:
            if boarding_complete:
                boarding_end = times['boarded_sec']
            elif status == 'failed_after_boarding':
                failures = transitions[pid]['failed_after_boarding']
                require(len(failures) == 1 and failures[0]['request_id'] == q['request_id'], 'Failure lacks unique observed event')
                boarding_end = float(failures[0]['time_sec'])
            else:
                boarding_end = horizon
            require(started <= boarding_end <= horizon, 'Invalid observed boarding duration')
            boarding_observed = boarding_end - started
        require(times['boarded_sec'] is None or started is not None, 'Completed boarding without start')
        details.append({'request_id': q['request_id'], 'person_id': pid, 'person_type': p['person_type'],
                        'request_final_status': status, 'person_final_status': p['status'], 'person_final_mode': p['mode'],
                        **times, 'wait_to_boarding_start_observed_sec': end - received,
                        'wait_observed_end_sec': end, 'wait_endpoint': kind, 'wait_right_censored_at_H': censored,
                        'boarding_duration_observed_sec': boarding_observed, 'boarding_completed': boarding_complete,
                        'origin_ped_closed_unboarded_including_boarding_sec': float(p['origin_ped_closed_wait_sec']),
                        'origin_vehicle_closed_unboarded_including_boarding_sec': float(p['origin_vehicle_closed_wait_sec']),
                        'cancel_reason': q['cancel_reason']})
    summaries = []
    distributions = []
    for group in ['type3', 'type4', 'all']:
        rows = [x for x in details if group == 'all' or x['person_type'] == group]
        waits = [x['wait_to_boarding_start_observed_sec'] for x in rows]
        summary = {'group': group, 'requests': len(rows),
                   'observed_wait_mean_sec': mean(waits) if waits else None,
                   'observed_wait_min_sec': min(waits) if waits else None,
                   'observed_wait_max_sec': max(waits) if waits else None,
                   'horizon_right_censored_preboarding': sum(x['wait_right_censored_at_H'] for x in rows),
                   'request_served': sum(x['request_final_status'] == 'served' for x in rows),
                   'person_admitted': sum(x['person_final_status'] == 'admitted' for x in rows),
                   'fallback_attempted': sum(x['fallback_sec'] is not None for x in rows)}
        for field in fields:
            summary[field.removesuffix('_sec') + '_observed_count'] = sum(x[field] is not None for x in rows)
        summaries.append(summary)
        for endpoint in sorted({x['wait_endpoint'] for x in rows}):
            counts = Counter(x['wait_to_boarding_start_observed_sec'] for x in rows if x['wait_endpoint'] == endpoint)
            cumulative = 0
            for seconds, count in sorted(counts.items()):
                cumulative += count
                distributions.append({'group': group, 'wait_endpoint': endpoint, 'observed_wait_sec': seconds,
                                      'count': count, 'endpoint_cumulative_count': cumulative,
                                      'all_request_denominator': len(rows),
                                      'cumulative_fraction_of_all_requests': cumulative / len(rows)})
    return details, summaries, distributions
