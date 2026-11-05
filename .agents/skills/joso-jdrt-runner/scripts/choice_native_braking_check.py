"""Read-only diagnostic consistency contract; never permits research adoption."""
import math
import re


PATTERN = (r"Warning: Vehicle '([^']+)' performs emergency braking on lane '([^']+)' "
           r"with decel=([0-9]+\.[0-9]{2}), wished=([0-9]+\.[0-9]{2}), "
           r"severity=([0-9]+\.[0-9]{2}), time=([0-9]+(?:\.[0-9]+)?)\.")


def check_warning(line, frames, step_sec, properties, numerical_eps, warning_threshold):
    """Check a warning against three consecutive raw frames and supplied properties.

    The caller must separately bind source/binary/options/type/property provenance.
    Numeric matches prove consistency, not a unique trigger, safety or adoption.
    """
    checks = {}
    result = dict(status='INCONSISTENT', checks=checks, core_adoption_permitted=False,
                  scope='Diagnostic kinematics only; source/property binding remains a caller obligation')
    match = re.fullmatch(PATTERN, line)
    checks['exact_message_shape'] = match is not None
    if match is None:
        return result
    checks['three_frames'] = len(frames) == 3
    if len(frames) != 3:
        return result
    try:
        at = float(match[6])
        decel, emergency = float(properties['decel']), float(properties['emergencyDecel'])
        speeds = [float(row['speed_mps']) for row in frames]
        distances = [float(row['distance_m']) for row in frames]
        times = [float(row['time_sec']) for row in frames]
        raw_decels = [float(row['decel_mps2']) for row in frames]
        numbers = [at, step_sec, decel, emergency, numerical_eps, warning_threshold,
                   *speeds, *distances, *times, *raw_decels,
                   *[float(match[i]) for i in (3, 4, 5)]]
        checks['finite_numeric_evidence'] = all(math.isfinite(n) for n in numbers)
        checks['positive_settings'] = step_sec > 0 and emergency >= decel > 0 and numerical_eps > 0 and warning_threshold > 0
        checks['nonnegative_motion'] = min(speeds) >= 0 and min(distances) >= 0
        checks['actor_and_phase'] = all(row['actor_id'] == match[1] and row['kind'] in ('car', 'drt')
                                       and row['phase'] == 'after_step_before_control' for row in frames)
        checks['warning_pre_move_lane'] = frames[1]['lane_id'] == match[2]
        checks['consecutive_native_step_clock'] = times == [at-step_sec, at, at+step_sec]
        checks['wished_property_matches_frames'] = all(value == decel for value in raw_decels)
        if not all(checks.values()):
            return result
        acceleration = (speeds[2] - speeds[1]) / step_sec
        previous_acceleration = (speeds[1] - speeds[0]) / step_sec
        checks['finite_derived_acceleration'] = math.isfinite(acceleration) and math.isfinite(previous_acceleration)
        if not checks['finite_derived_acceleration']:
            return result
        # Floating arithmetic allowances are derived from the recorded doubles,
        # not a physical braking tolerance or the observed research result.
        accel_roundoff = 16 * max(math.ulp(speeds[1]), math.ulp(speeds[2])) / step_sec
        euler = speeds[2] * step_sec
        residual = distances[2] - distances[1] - euler
        distance_roundoff = 32 * max(math.ulp(distances[1]), math.ulp(distances[2]), math.ulp(euler))
        checks['within_supplied_emergency_bound'] = -acceleration <= emergency + accel_roundoff
        checks['new_braking_manoeuvre'] = acceleration + numerical_eps < previous_acceleration
        checks['beyond_wished_deceleration'] = -acceleration - decel - numerical_eps > 0
        severity = (-acceleration - decel + numerical_eps) / max(numerical_eps, emergency-decel)
        checks['source_warning_threshold'] = severity >= warning_threshold
        # Native diagnostics print two decimal places. Strict rounding cells
        # reject boundary/tie ambiguity rather than inventing extra precision.
        checks['printed_deceleration'] = abs(-acceleration - float(match[3])) < .5 * 10**-2
        checks['printed_wished'] = abs(decel - float(match[4])) < .5 * 10**-2
        checks['printed_severity'] = abs(severity - float(match[5])) < .5 * 10**-2
        checks['native_euler_distance'] = abs(residual) <= distance_roundoff
        result.update(derived_acceleration_mps2=acceleration,
                      previous_acceleration_mps2=previous_acceleration,
                      source_severity=severity, distance_residual_m=residual,
                      acceleration_roundoff_allowance=accel_roundoff,
                      distance_roundoff_allowance_m=distance_roundoff)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        checks['complete_numeric_frame_schema'] = False
        result['error_type'] = type(error).__name__
    if checks and all(checks.values()):
        result['status'] = 'DIAGNOSTIC_MATCH'
    return result
