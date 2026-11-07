"""SP-14 parent loop: artificial fake core_sequence only; no research CLI, no native, no network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import choice_core_sequence as core
import choice_parent_loop as parent

MONITOR_DIR = Path(__file__).resolve().parents[4] / '07_監視システム'
EXPECTED = {'status': 'COMPLETED_REGISTERED_SCOPE_PENDING_ANALYSIS', 'completed': 1, 'goal_complete': False}
SENTINEL = 'SENTINEL_RESEARCH_VALUE'  # a research-like value that must never reach a stop/event


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class FakeWorld:
    """Temporary project root with an artificial registration and a fake core_sequence runner."""

    def __init__(self, root, cells=4, recorded=1):
        self.root = Path(root)
        self.cfg = {'protocol': 'realtime_choice_v1', 'municipality_code': '08211',
                    'registration_id': 'artificial_registration', 'workspace': 'ws',
                    'record_files': ['records/a.md', 'records/ledger.jsonl'],
                    'cells': [{'cell_id': f'artificial_{i}'} for i in range(cells)]}
        write(self.root / core.CONFIG, self.cfg)
        self.workspace = self.root / 'ws'
        self.ledger_path = self.root / 'records/ledger.jsonl'
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text('', encoding='utf-8')
        for index in range(recorded):
            self.append_row(index, f'old{index + 1:02d}')
        self.prior = self.root / core.GOAL / 'core_sequence_evidence/seed/seed_record7_readback.json'
        write(self.prior, self.proof(self.rows()))
        self.plan = []
        self.calls = []

    def row(self, index, run_id):
        return {'protocol': self.cfg['protocol'], 'registration_id': self.cfg['registration_id'],
                'cell_id': self.cfg['cells'][index]['cell_id'], 'run_id': run_id,
                'validation_status': 'PASS', 'facility_accepted': SENTINEL}

    def append_row(self, index, run_id):
        with self.ledger_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(self.row(index, run_id)) + '\n')

    def rows(self):
        return [json.loads(x) for x in self.ledger_path.read_text(encoding='utf-8').splitlines() if x.strip()]

    def next_cell(self, count):
        return self.cfg['cells'][count] if count < len(self.cfg['cells']) else None

    def proof(self, rows):
        return {'status': 'RECORD7_PRIMARY_READBACK_PASS', 'run_id': rows[-1]['run_id'],
                'registration_id': self.cfg['registration_id'], 'recorded_cells': len(rows),
                'formal_row': rows[-1], 'six_document_single_markers': True,
                'unique_current_registration_ledger': True, 'source_common5_current': True,
                'all_status_holds_clear_at_finish': True,
                'original_and_record_validation_components_differ': [],
                'next_cell': self.next_cell(len(rows))}

    def status(self, count, **changes):
        value = dict(registered_cells=len(self.cfg['cells']), recorded_cells=count,
                     next_cell=self.next_cell(count), core_ready=True,
                     core_start_available=self.next_cell(count) is not None,
                     **{key: [] for key in core.HOLDS})
        value.update(changes)
        return value

    def runner(self, argv, stdout_path, stderr_path, cwd):
        self.calls.append(list(argv))
        mode = self.plan.pop(0) if self.plan else 'ok'
        if mode == 'raise':
            raise OSError('artificial launch failure')
        sid = argv[argv.index('--sequence-id') + 1]
        prefix = argv[argv.index('--prefix') + 1]
        count = int(argv[argv.index('--expected-recorded') + 1])
        run_id = prefix + str(count + 1).zfill(2)
        operation = self.workspace / 'driver_logs/core_sequences' / sid
        operation.mkdir(parents=True)
        evidence = self.root / core.GOAL / 'core_sequence_evidence' / sid
        evidence.mkdir(parents=True)
        Path(stderr_path).write_text('', encoding='utf-8')
        if mode == 'fail_core':
            write(operation / 'state.json', {'status': 'FAILED_PRESERVED', 'phase': 'core',
                                             'error_type': 'RuntimeError',
                                             'error': 'Core monitor anomaly; preserve and stop subsequent starts',
                                             'child_may_still_be_running': True,
                                             'active': {'run_id': run_id}, 'completed': []})
            Path(stdout_path).write_text('', encoding='utf-8')
            return 1
        if mode != 'no_ledger':
            self.append_row(count, run_id)
        rows = self.rows()
        proof = self.proof(rows)
        if mode == 'bad_readback':
            proof['status'] = 'INVALID'
        readback = evidence / (run_id + '_record7_readback.json')
        write(readback, proof)
        changes = {'unrecorded': [run_id]} if mode == 'hold_after' else {}
        status_log = operation / '0050.stdout.log'
        write(status_log, self.status(len(rows), **changes))
        command = {'argv': ['python', 'realtime_choice_cell.py', 'status'],
                   'stdout': status_log.as_posix(), 'exit_code': 0}
        if mode == 'no_status':
            command['argv'][-1] = '--check'
        completed_run = 'someone_else' if mode == 'wrong_run' else run_id
        write(operation / 'state.json', {'status': 'COMPLETED_REGISTERED_SCOPE_PENDING_ANALYSIS',
                                         'phase': 'sync', 'active': None, 'goal_complete': False,
                                         'completed': [{'run_id': completed_run,
                                                        'cell': self.cfg['cells'][count],
                                                        'readback': readback.as_posix()}],
                                         'command': command})
        stdout = dict(EXPECTED, completed=2) if mode == 'bad_stdout' else EXPECTED
        Path(stdout_path).write_text(json.dumps(stdout) + '\n', encoding='utf-8')
        return 0


class Harness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.world = FakeWorld(self.temp.name)
        self.events = []
        self.monitor_ok = True

    def monitor(self):
        if not self.monitor_ok:
            raise parent.ParentStop('MONITOR_NOT_PROVEN', 'artificial stale observer')
        return {'observation_age_sec': 1}

    def writer(self, kind, target, evidence):
        self.events.append((kind, target, evidence))
        return 'artificial_event_path'

    def loop(self, prior='default', settings=None, prefix='np2611'):
        prior = self.world.prior if prior == 'default' else prior
        return parent.ParentLoop(self.world.root, prefix, prior_readback=prior, settings_path=settings,
                                 runner=self.world.runner, event_writer=self.writer,
                                 monitor_check=self.monitor)

    def directory(self):
        return self.world.workspace / parent.PARENT_DIR

    def stop_records(self):
        folder = self.directory() / 'stops'
        if not folder.exists():
            return []
        return [json.loads(p.read_text(encoding='utf-8'))
                for p in sorted(folder.glob('*.json')) if p.name.count('.') == 1]

    def last_stop(self):
        records = self.stop_records()
        self.assertTrue(records, 'a stop record must be preserved')
        return records[-1]

    def assert_stopped(self, code, calls):
        result = self.loop().run()
        self.assertEqual(result, parent.EXIT_STOPPED)
        stop = self.last_stop()
        self.assertEqual(stop['code'], code)
        self.assertEqual(len(self.world.calls), calls)
        kinds = [event[0] for event in self.events]
        self.assertEqual(kinds, ['parent_stopped'])
        return stop


class HappyPath(Harness):
    def test_runs_one_cell_per_call_in_registered_order_then_notifies_completion(self):
        self.assertEqual(self.loop().run(), parent.EXIT_COMPLETE)
        self.assertEqual(len(self.world.calls), 3)
        for index, argv in enumerate(self.world.calls):
            self.assertEqual(argv[argv.index('--max-cells') + 1], '1')
            self.assertEqual(argv[argv.index('--expected-recorded') + 1], str(index + 1))
            self.assertTrue(argv[4].endswith('choice_core_sequence.py'))
        self.assertEqual([row['run_id'] for row in self.world.rows()],
                         ['old01', 'np261102', 'np261103', 'np261104'])
        # Each call receives the readback produced by the previous call.
        second = self.world.calls[1]
        self.assertTrue(second[second.index('--prior-readback') + 1].endswith('np261102_record7_readback.json'))
        self.assertEqual([event[0] for event in self.events], ['all_complete'])
        evidence = self.events[0][2]
        self.assertIn('分析は未実施', evidence['status'])
        self.assertTrue((self.directory() / 'parent_complete.json').exists())
        self.assertEqual(self.stop_records(), [])

    def test_parent_never_calls_research_cli_commands(self):
        self.loop().run()
        forbidden = {'status', 'start-next', 'check', 'validate', 'record', 'reject', 'recover',
                     'recover-launch', 'recover-writer', 'recover-record', 'preflight'}
        for argv in self.world.calls:
            self.assertFalse(forbidden & set(argv), argv)
            self.assertFalse(any('realtime_choice_cell' in part or 'choice_finish_cell' in part for part in argv))

    def test_restart_after_completion_is_idempotent_and_starts_nothing(self):
        self.loop().run()
        calls = len(self.world.calls)
        self.assertEqual(self.loop(prior=None).run(), parent.EXIT_COMPLETE)
        self.assertEqual(len(self.world.calls), calls)
        targets = {event[1] for event in self.events}
        self.assertEqual(len(targets), 1, 'same event target, so the monitor event is written once')


class StopsAndPreservation(Harness):
    def test_sequence_failure_stops_without_any_rerun_or_recovery(self):
        self.world.plan = ['fail_core']
        stop = self.assert_stopped('SEQUENCE_FAILED', calls=1)
        self.assertEqual(stop['detail_code'], 'CORE_ANOMALY')
        self.assertTrue(stop['sequence']['child_may_still_be_running'])
        self.assertEqual(stop['iteration']['run_id'], 'np261102')
        self.assertIn('sequence_exited', stop['iteration']['steps_done'])
        self.assertNotIn('sequence_state_checked', stop['iteration']['steps_done'])
        self.assertIn('SEQUENCE_FAILED', self.events[0][2]['status'])

    def test_unexpected_stdout_stops(self):
        self.world.plan = ['bad_stdout']
        self.assert_stopped('SEQUENCE_OUTPUT_UNEXPECTED', calls=1)

    def test_sequence_state_for_another_run_stops(self):
        self.world.plan = ['wrong_run']
        self.assert_stopped('SEQUENCE_STATE_MISMATCH', calls=1)

    def test_readback_not_pass_stops(self):
        self.world.plan = ['bad_readback']
        self.assert_stopped('READBACK_MISMATCH', calls=1)

    def test_partial_record_without_ledger_row_stops(self):
        self.world.plan = ['no_ledger']
        stop = self.assert_stopped('LEDGER_MISMATCH', calls=1)
        self.assertEqual(stop['evidence']['ledger_rows'], 1)

    def test_post_record_hold_stops_and_names_the_hold(self):
        self.world.plan = ['hold_after']
        stop = self.assert_stopped('POST_STATUS_HOLD', calls=1)
        self.assertEqual(stop['evidence']['nonempty_holds'], ['unrecorded'])

    def test_missing_post_record_status_is_not_assumed_clear(self):
        self.world.plan = ['no_status']
        self.assert_stopped('POST_STATUS_UNAVAILABLE', calls=1)

    def test_monitor_not_proven_stops_before_any_call(self):
        self.monitor_ok = False
        self.assert_stopped('MONITOR_NOT_PROVEN', calls=0)

    def test_prior_readback_mismatch_stops_before_any_call(self):
        write(self.world.prior, dict(self.world.proof(self.world.rows()), recorded_cells=7))
        self.assert_stopped('PRIOR_READBACK_INVALID', calls=0)

    def test_ledger_out_of_registered_order_or_not_pass_stops(self):
        original = self.world.rows()[0]
        for change in ({'cell_id': 'artificial_3'}, {'validation_status': 'INVALID'},
                       {'registration_id': 'foreign'}):
            with self.subTest(change=change):
                self.events.clear()
                folder = self.directory() / 'stops'
                if folder.exists():
                    for path in folder.glob('*'):
                        path.unlink()
                self.world.ledger_path.write_text(json.dumps(dict(original, **change)) + '\n', encoding='utf-8')
                self.assert_stopped('LEDGER_INVALID', calls=0)

    def test_used_run_id_stops_before_any_call(self):
        (self.world.workspace / 'runs/np261102').mkdir(parents=True)
        self.assert_stopped('RUN_ID_IN_USE', calls=0)

    def test_runner_exception_is_preserved_as_internal_error(self):
        self.world.plan = ['raise']
        stop = self.assert_stopped('INTERNAL_ERROR', calls=1)
        self.assertEqual(stop['evidence']['error_type'], 'OSError')

    def test_stop_is_atomic_and_mirrors_parent_stop_json(self):
        self.world.plan = ['fail_core']
        self.loop().run()
        stop = self.last_stop()
        mirror = json.loads((self.directory() / 'parent_stop.json').read_text(encoding='utf-8'))
        self.assertEqual(mirror, stop)
        self.assertFalse(list(self.directory().rglob('*.tmp')))
        for key in ('stop_id', 'code', 'reason', 'at_jst', 'iteration', 'actions_taken'):
            self.assertIn(key, stop)

    def test_stop_and_event_never_carry_research_values(self):
        self.world.plan = ['hold_after']
        self.loop().run()
        text = json.dumps(self.last_stop(), ensure_ascii=False) + json.dumps(self.events, ensure_ascii=False)
        self.assertNotIn(SENTINEL, text)

    def test_notification_failure_still_preserves_the_stop(self):
        def broken(kind, target, evidence):
            raise OSError('artificial events folder failure')
        self.world.plan = ['fail_core']
        loop = self.loop()
        loop.event_writer = broken
        self.assertEqual(loop.run(), parent.EXIT_STOPPED)
        stop = self.last_stop()
        notify = json.loads((self.directory() / 'stops' / (stop['stop_id'] + '.notify.json')).read_text(encoding='utf-8'))
        self.assertEqual(notify['error_type'], 'OSError')

    def test_previous_parent_interrupted_mid_iteration_stops_without_resuming(self):
        write(self.directory() / 'parent_state.json', {'phase': 'sequence_running', 'session_id': 'old',
                                                        'iteration': {'run_id': 'np261102'}})
        stop = self.assert_stopped('PREVIOUS_PARENT_INTERRUPTED', calls=0)
        self.assertEqual(stop['evidence']['previous_state']['iteration']['run_id'], 'np261102')

    def test_completion_without_sequence_evidence_is_not_announced(self):
        world = self.world
        for index in range(1, len(world.cfg['cells'])):
            world.append_row(index, f'manual{index}')
        write(world.prior, world.proof(world.rows()))
        self.assert_stopped('COMPLETION_UNPROVEN', calls=0)
        self.assertIn('COMPLETION_UNPROVEN', self.events[0][2]['status'])


class AcknowledgeAndLock(Harness):
    def test_unacknowledged_stop_refuses_restart_without_new_event(self):
        self.world.plan = ['fail_core']
        self.loop().run()
        self.events.clear()
        self.assertEqual(self.loop().run(), parent.EXIT_UNACKED)
        self.assertEqual(len(self.world.calls), 1)
        self.assertEqual(self.events, [])

    def test_ack_requires_a_reason_and_is_the_only_resume_path(self):
        self.world.plan = ['fail_core']
        self.loop().run()
        stop = self.last_stop()
        for reason in ('', '   ', None):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                parent.acknowledge(self.world.root, stop['stop_id'], reason)
        with self.assertRaises(ValueError):
            parent.acknowledge(self.world.root, 'no_such_stop', 'reason')
        parent.acknowledge(self.world.root, stop['stop_id'], '人が原因を解消し、再実行は別途指示で実施済み')
        with self.assertRaises(ValueError):
            parent.acknowledge(self.world.root, stop['stop_id'], 'twice')
        self.assertEqual(len(self.world.calls), 1, 'ack itself never runs anything')
        ack = json.loads((self.directory() / 'stops' / (stop['stop_id'] + '.ack.json')).read_text(encoding='utf-8'))
        self.assertIn('再実行', ack['reason'])
        # The failed fake left no ledger row; restart proceeds from the preserved ledger with a new prefix.
        self.events.clear()
        self.assertEqual(self.loop(prefix='nq2611').run(), parent.EXIT_COMPLETE)

    def test_second_parent_does_nothing_while_the_lock_is_held(self):
        self.directory().mkdir(parents=True)
        holder = parent.ParentLock(self.directory() / 'parent.lock')
        try:
            self.assertEqual(self.loop().run(), parent.EXIT_LOCKED)
            with self.assertRaises(RuntimeError):
                parent.acknowledge(self.world.root, 'any', 'reason')
        finally:
            holder.close()
        self.assertEqual(self.world.calls, [])
        self.assertEqual(self.events, [])
        self.assertFalse((self.directory() / 'stops').exists())
        again = parent.ParentLock(self.directory() / 'parent.lock')
        again.close()


class Checkpoint(Harness):
    def settings(self, value):
        path = Path(self.temp.name) / 'parent_settings.json'
        write(path, value)
        return path

    def test_no_checkpoint_by_default(self):
        self.assertEqual(self.loop().run(), parent.EXIT_COMPLETE)

    def test_configured_checkpoint_stops_once_and_resumes_after_ack(self):
        path = self.settings({'schema': 'choice_parent_loop_settings_v1', 'checkpoint_recorded_counts': [2]})
        self.assertEqual(self.loop(settings=path).run(), parent.EXIT_STOPPED)
        stop = self.last_stop()
        self.assertEqual(stop['code'], 'CHECKPOINT_REACHED')
        self.assertEqual(stop['evidence']['recorded_cells'], 2)
        self.assertEqual(len(self.world.calls), 1)
        parent.acknowledge(self.world.root, stop['stop_id'], '出力を確認した')
        self.assertEqual(self.loop(prior=None, settings=path).run(), parent.EXIT_COMPLETE)
        self.assertEqual(len(self.world.calls), 3)
        self.assertEqual([s['code'] for s in self.stop_records()], ['CHECKPOINT_REACHED'])

    def test_invalid_settings_are_refused_before_anything_runs(self):
        for value in ({'checkpoint_recorded_counts': [4]}, {'checkpoint_recorded_counts': [0]},
                      {'checkpoint_recorded_counts': [True]}, {'checkpoint_recorded_counts': '2'},
                      {'checkpoint_recorded_counts': [2], 'unknown': 1}):
            with self.subTest(value=value):
                path = self.settings(dict({'schema': 'choice_parent_loop_settings_v1'}, **value))
                self.assertEqual(self.loop(settings=path).run(), parent.EXIT_USAGE)
        self.assertEqual(self.world.calls, [])


class Helpers(unittest.TestCase):
    def test_sequence_errors_map_to_detail_codes_and_unknown_stays_unclassified(self):
        cases = {'Unresolved or missing status hold; preserve and stop': 'STATUS_HOLD',
                 'Independent observer identity/liveness/freshness not proven': 'MONITOR_NOT_PROVEN',
                 'Independent target discovery remains unproven': 'MONITOR_TARGET_NOT_DISCOVERED',
                 'Pinned source/config changed; no subsequent command permitted': 'PINNED_SHA_CHANGED',
                 'Command failed; inspect its original logs, never replay automatically': 'CHILD_COMMAND_FAILED',
                 'something new': 'UNCLASSIFIED'}
        for message, code in cases.items():
            with self.subTest(message=message):
                self.assertEqual(parent.classify_sequence_error(message), code)


class DefaultMonitorAndEvents(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.world = FakeWorld(self.base / 'project')
        self.runtime = self.base / 'runtime'
        self.config = self.base / 'monitor_config.json'
        write(self.config, {'runtime': str(self.runtime), 'mail_enabled': True})
        self.watch_path = MONITOR_DIR / 'watch.py'
        self.identity = {'state': 'alive', 'pid': 42, 'created': 7}

    def loop(self, clock_value):
        return parent.ParentLoop(self.world.root, 'np2611', prior_readback=self.world.prior,
                                 monitor_config=self.config, watch_path=self.watch_path,
                                 probe=lambda pid: dict(self.identity), clock=lambda: clock_value)

    def state(self, **changes):
        value = {'observed_epoch': 1000.0, 'monitor_pid': 42, 'monitor_identity': dict(self.identity),
                 'monitor_source_sha256': core.digest(self.watch_path)}
        value.update(changes)
        write(self.runtime / 'state.json', value)

    def test_fresh_live_same_source_monitor_passes(self):
        self.state()
        self.loop(1010.0).default_monitor_check()

    def test_stale_restarted_or_other_source_monitor_stops(self):
        for changes, clock in (({}, 1121.0),
                               ({'monitor_identity': {'state': 'alive', 'pid': 42, 'created': 8}}, 1010.0),
                               ({'monitor_source_sha256': 'other'}, 1010.0)):
            with self.subTest(changes=changes):
                self.state(**changes)
                with self.assertRaises(parent.ParentStop) as raised:
                    self.loop(clock).default_monitor_check()
                self.assertEqual(raised.exception.code, 'MONITOR_NOT_PROVEN')
        (self.runtime / 'state.json').unlink()
        with self.assertRaises(parent.ParentStop):
            self.loop(1010.0).default_monitor_check()

    def test_default_event_uses_monitor_schema_without_ai_and_reaches_mail_outbox(self):
        loop = self.loop(1010.0)
        path = Path(loop.default_event_writer('parent_stopped', 'choice-parent-stop:x',
                                              {'target_id': 'choice_parent_loop', 'status': 'STOP', 'source': 's'}))
        event = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(event['schema'], 'simulation_watch_event_v1')
        self.assertEqual(event['kind'], 'parent_stopped')
        self.assertEqual(event['delivery'], 'not_applicable')
        self.assertFalse(event['research_adoption'])
        sys.path.insert(0, str(MONITOR_DIR))
        try:
            import watch
            self.assertEqual(watch.sync_mail_outbox({'mail_enabled': True}, self.runtime), 1)
        finally:
            sys.path.remove(str(MONITOR_DIR))


if __name__ == '__main__':
    unittest.main()
