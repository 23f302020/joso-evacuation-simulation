"""SP-14 parent loop: artificial fake core_sequence only; no research CLI, no native, no network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def mail(self):
        if not getattr(self, 'mail_ok', True):
            raise parent.ParentStop('MAIL_PATH_NOT_READY', 'artificial broken mail path')
        return {'mail_path': 'ready'}

    def loop(self, prior='default', settings=None, prefix='np2611'):
        prior = self.world.prior if prior == 'default' else prior
        loop = parent.ParentLoop(self.world.root, prefix, prior_readback=prior, settings_path=settings,
                                 runner=self.world.runner, event_writer=self.writer,
                                 monitor_check=self.monitor)
        loop.mail_check = self.mail  # injected like monitor_check (SP-14 review D2)
        return loop

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

    def test_progress_mail_is_off_by_default(self):
        self.assertEqual(self.loop().run(), parent.EXIT_COMPLETE)
        self.assertNotIn('parent_progress', [event[0] for event in self.events])

    def test_progress_mail_never_stops_and_is_sent_once_per_count_without_results(self):
        loop = self.loop()
        loop.progress_every = 1
        self.assertEqual(loop.run(), parent.EXIT_COMPLETE)
        progress = [event for event in self.events if event[0] == 'parent_progress']
        self.assertEqual([event[2]['recorded_cells'] for event in progress], [1, 2, 3])  # 4 = complete, not progress
        self.assertEqual(len({event[1] for event in progress}), 3)  # idempotent key per count
        self.assertIn('止まらずに続行', progress[0][2]['status'])
        self.assertIn('時点の進捗', progress[0][2]['status'])  # a late-delivered mail still says when it was true
        self.assertIn('見込みは未算出', progress[0][2]['status'])  # no cell finished in this session yet
        self.assertRegex(progress[2][2]['status'], r'平均\d+分/セル')
        self.assertEqual([event[0] for event in self.events][-1], 'all_complete')
        self.assertEqual(self.stop_records(), [])

    def test_progress_every_n_skips_other_counts(self):
        loop = self.loop()
        loop.progress_every = 2
        self.assertEqual(loop.run(), parent.EXIT_COMPLETE)
        self.assertEqual([e[2]['recorded_cells'] for e in self.events if e[0] == 'parent_progress'], [2])

    def test_progress_mail_failure_does_not_stop_the_run(self):
        def broken(kind, target, evidence):
            if kind == 'parent_progress':
                raise OSError('artificial events folder failure')
            return self.writer(kind, target, evidence)
        loop = self.loop()
        loop.progress_every = 1
        loop.event_writer = broken
        self.assertEqual(loop.run(), parent.EXIT_COMPLETE)
        self.assertEqual(len(self.world.calls), 3)
        rows = [json.loads(line) for line in (self.directory() / 'parent_operations.jsonl').read_text(
            encoding='utf-8').splitlines()]
        failed = [r for r in rows if r['action'] == 'parent_progress' and r['notification'].get('error_type')]
        self.assertEqual(len(failed), 3)

    def test_invalid_progress_every_is_off(self):
        for value in (0, -1, True, '2', None):
            with self.subTest(value=value):
                loop = parent.ParentLoop(self.world.root, 'np2611', progress_every=value)
                self.assertEqual(loop.progress_every, 0)

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


class CompletionEvidence(Harness):
    """Review F1: a last cell finished by a human can still be proven complete, with provenance."""

    def setUp(self):
        super().setUp()
        self.world = FakeWorld(self.temp.name + '/f1', cells=3, recorded=1)
        self.world.plan = ['ok', 'fail_core']
        self.assertEqual(self.loop().run(), parent.EXIT_STOPPED)
        # Human, outside the parent: finishes the last cell and keeps the readback and a status output.
        self.world.append_row(2, 'manual03')
        self.manual = self.world.root / core.GOAL / 'core_sequence_evidence/manual/manual03_record7_readback.json'
        write(self.manual, self.world.proof(self.world.rows()))
        self.status_path = Path(self.temp.name) / 'human_status.json'
        write(self.status_path, self.world.status(3))
        parent.acknowledge(self.world.root, self.last_stop()['stop_id'], '人が最終セルをfinishし読戻しを保存した')
        self.events.clear()

    def human_loop(self, readback=True, status=True):
        loop = self.loop(prior=str(self.manual) if readback else None)
        loop.completion_status = self.status_path if status else None
        return loop

    def test_human_readback_and_status_prove_completion_with_provenance(self):
        self.assertEqual(self.human_loop().run(), parent.EXIT_COMPLETE)
        record = json.loads((self.directory() / 'parent_complete.json').read_text(encoding='utf-8'))
        self.assertEqual(record['provenance'], 'human_provided')
        self.assertEqual(record['human_evidence']['completion_status_sha256'], core.digest(self.status_path))
        self.assertEqual(record['human_evidence']['readback_sha256'], core.digest(self.manual))
        self.assertEqual([e[0] for e in self.events], ['all_complete'])

    def test_restart_after_human_completion_is_idempotent_but_rechecks_the_evidence(self):
        self.assertEqual(self.human_loop().run(), parent.EXIT_COMPLETE)
        self.events.clear()
        self.assertEqual(self.loop(prior=None).run(), parent.EXIT_COMPLETE)
        self.assertEqual(self.stop_records()[-1]['code'], 'SEQUENCE_FAILED', 'no new stop')
        write(self.status_path, self.world.status(3, unrecorded=['manual03']))  # evidence changed afterwards
        self.assertEqual(self.loop(prior=None).run(), parent.EXIT_STOPPED)
        self.assertEqual(self.last_stop()['code'], 'COMPLETION_UNPROVEN')

    def test_readback_without_human_status_stays_unproven(self):
        self.assertEqual(self.human_loop(status=False).run(), parent.EXIT_STOPPED)
        stop = self.last_stop()
        self.assertEqual(stop['code'], 'COMPLETION_UNPROVEN')
        self.assertIn('--completion-status', stop['reason'])
        self.assertNotIn('all_complete', [e[0] for e in self.events])

    def test_human_status_with_a_hold_is_not_completion(self):
        write(self.status_path, self.world.status(3, unrecorded=['manual03']))
        self.assertEqual(self.human_loop().run(), parent.EXIT_STOPPED)
        self.assertEqual(self.last_stop()['code'], 'COMPLETION_UNPROVEN')
        self.assertNotIn('all_complete', [e[0] for e in self.events])

    def test_human_readback_must_prove_all_cells(self):
        write(self.manual, dict(self.world.proof(self.world.rows()), recorded_cells=2))
        self.assertEqual(self.human_loop().run(), parent.EXIT_STOPPED)
        self.assertEqual(self.last_stop()['code'], 'COMPLETION_UNPROVEN')

    def test_parent_executed_completion_records_its_provenance(self):
        world = FakeWorld(self.temp.name + '/plain')
        self.world = world
        self.assertEqual(self.loop().run(), parent.EXIT_COMPLETE)
        record = json.loads((self.directory() / 'parent_complete.json').read_text(encoding='utf-8'))
        self.assertEqual(record['provenance'], 'parent_executed')


class SettingsPersistence(Harness):
    """Review F2: checkpoints survive restarts; changes need an explicit, reasoned ack."""

    def settings(self, counts, name='settings.json'):
        path = Path(self.temp.name) / name
        write(path, {'schema': parent.SETTINGS_SCHEMA, 'checkpoint_recorded_counts': counts})
        return path

    def readback_of(self, run_id):
        return str(next((self.world.root / core.GOAL / 'core_sequence_evidence').glob(f'*/{run_id}_record7_readback.json')))

    def test_first_run_stores_settings_content_and_sha(self):
        path = self.settings([2])
        self.loop(settings=path).run()
        stored = json.loads((self.directory() / 'parent_settings.json').read_text(encoding='utf-8'))
        self.assertEqual(stored['settings'], {'checkpoint_recorded_counts': [2]})
        self.assertEqual(stored['source_sha256'], core.digest(path))
        self.assertTrue(stored['sha256'])

    def test_restart_without_settings_cannot_skip_a_checkpoint(self):
        path = self.settings([3])
        self.world.plan = ['ok', 'hold_after']  # third record lands, then a post-record hold stops
        self.assertEqual(self.loop(settings=path).run(), parent.EXIT_STOPPED)
        parent.acknowledge(self.world.root, self.last_stop()['stop_id'], 'hold を人が解消')
        self.assertEqual(self.loop(prior=self.readback_of('np261103'), prefix='np2612').run(), parent.EXIT_USAGE)
        self.assertEqual(len(self.world.rows()), 3)
        self.assertEqual(len(self.world.calls), 2)
        self.assertEqual(self.loop(prior=self.readback_of('np261103'), settings=path, prefix='np2612').run(),
                         parent.EXIT_STOPPED)
        self.assertEqual(self.last_stop()['code'], 'CHECKPOINT_REACHED')
        self.assertEqual(len(self.world.calls), 2)

    def test_different_settings_are_refused(self):
        self.loop(settings=self.settings([2])).run()
        parent.acknowledge(self.world.root, self.last_stop()['stop_id'], 'checked')
        self.assertEqual(self.loop(prior=None, settings=self.settings([3], 'other.json')).run(), parent.EXIT_USAGE)
        self.assertEqual(len(self.world.calls), 1)

    def test_settings_change_only_through_a_reasoned_ack(self):
        self.loop(settings=self.settings([2])).run()
        stop = self.last_stop()
        new = self.settings([3], 'new.json')
        ack = parent.acknowledge(self.world.root, stop['stop_id'], 'チェックポイントを3件目へ移す', settings_path=new)
        self.assertEqual(ack['settings_change']['new_settings'], {'checkpoint_recorded_counts': [3]})
        self.assertNotEqual(ack['settings_change']['previous_sha256'], ack['settings_change']['new_sha256'])
        self.assertEqual(self.loop(prior=None).run(), parent.EXIT_USAGE)  # still needs the same settings
        self.assertEqual(self.loop(prior=None, settings=new).run(), parent.EXIT_STOPPED)
        self.assertEqual(self.last_stop()['code'], 'CHECKPOINT_REACHED')
        self.assertEqual(self.last_stop()['evidence']['recorded_cells'], 3)
        parent.acknowledge(self.world.root, self.last_stop()['stop_id'], 'チェックポイントをなくす',
                           clear_settings=True)
        self.assertEqual(self.loop(prior=None).run(), parent.EXIT_COMPLETE)

    def test_invalid_settings_change_is_refused(self):
        self.loop(settings=self.settings([2])).run()
        stop = self.last_stop()
        with self.assertRaises(ValueError):
            parent.acknowledge(self.world.root, stop['stop_id'], 'bad', settings_path=self.settings([9], 'bad.json'))
        with self.assertRaises(ValueError):
            parent.acknowledge(self.world.root, stop['stop_id'], 'both', settings_path=self.settings([3], 'x.json'),
                               clear_settings=True)


class StopNotificationRobustness(Harness):
    """Review F3 and D6: a preserved stop is always notified; stop records are never overwritten."""

    def flaky(self, failing_name):
        original = parent.atomic_write
        def writer(path, value):
            if Path(path).name == failing_name:
                raise PermissionError('artificial: held open by a reader')
            return original(path, value)
        return patch.object(parent, 'atomic_write', side_effect=writer)

    def test_mirror_write_failure_still_notifies(self):
        self.world.plan = ['fail_core']
        with self.flaky('parent_stop.json'):
            self.assertEqual(self.loop().run(), parent.EXIT_STOPPED)
        stop = self.last_stop()
        self.assertEqual([e[0] for e in self.events], ['parent_stopped'])
        notify = json.loads((self.directory() / 'stops' / (stop['stop_id'] + '.notify.json')).read_text(encoding='utf-8'))
        self.assertEqual(notify['mirror_error']['error_type'], 'PermissionError')

    def test_state_write_failure_still_notifies(self):
        with self.flaky('parent_state.json'):
            self.assertEqual(self.loop().run(), parent.EXIT_STOPPED)
        self.assertEqual([e[0] for e in self.events], ['parent_stopped'])

    def test_unnotified_stop_is_notified_again_at_startup(self):
        self.world.plan = ['fail_core']
        self.loop().run()
        stop = self.last_stop()
        (self.directory() / 'stops' / (stop['stop_id'] + '.notify.json')).unlink()
        self.events.clear()
        self.assertEqual(self.loop().run(), parent.EXIT_UNACKED)
        self.assertEqual([(e[0], e[1]) for e in self.events], [('parent_stopped', 'choice-parent-stop:' + stop['stop_id'])])
        notify = json.loads((self.directory() / 'stops' / (stop['stop_id'] + '.notify.json')).read_text(encoding='utf-8'))
        self.assertTrue(notify['resent'])
        self.events.clear()
        self.assertEqual(self.loop().run(), parent.EXIT_UNACKED)
        self.assertEqual(self.events, [], 'a notified stop is not notified again')

    def test_stop_record_write_failure_still_attempts_notification(self):
        self.world.plan = ['fail_core']
        with patch.object(parent, 'create_exclusive', side_effect=PermissionError('artificial disk failure')):
            with self.assertRaises(PermissionError):
                self.loop().run()
        self.assertEqual([e[0] for e in self.events], ['parent_stopped'])
        self.events.clear()
        self.assertEqual(self.loop().run(), parent.EXIT_STOPPED)
        self.assertEqual(self.last_stop()['code'], 'PREVIOUS_PARENT_INTERRUPTED')

    def test_existing_stop_record_is_never_overwritten(self):
        folder = self.directory() / 'stops'
        write(folder / 'plfixed_01.json', {'stop_id': 'plfixed_01', 'code': 'OLD_ACKED_STOP'})
        write(folder / 'plfixed_01.ack.json', {'stop_id': 'plfixed_01', 'reason': 'old'})
        write(folder / 'plfixed_01.notify.json', {'event': 'old'})
        before = (folder / 'plfixed_01.json').read_bytes()
        self.world.plan = ['fail_core']
        loop = self.loop()
        loop.session_id = 'plfixed'
        self.assertEqual(loop.run(), parent.EXIT_STOPPED)
        self.assertEqual((folder / 'plfixed_01.json').read_bytes(), before)
        self.assertEqual(self.last_stop()['stop_id'], 'plfixed_02')
        self.assertEqual(self.last_stop()['code'], 'SEQUENCE_FAILED')


class MailPathPrecheck(Harness):
    """Review D2: never start unattended work while stops would be silent."""

    def test_broken_mail_path_stops_before_any_call(self):
        self.mail_ok = False
        self.assert_stopped('MAIL_PATH_NOT_READY', calls=0)


class DefaultMailCheck(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()  # patterns are compared with the resolved workspace (8.3 short TEMP)
        self.world = FakeWorld(base / 'project')
        self.runtime = base / 'runtime'
        self.config_path = base / 'monitor_config.json'
        self.config = {'runtime': str(self.runtime), 'mail_enabled': True, 'mail_to': 'artificial@example.invalid',
                       'patterns': [str(self.world.workspace / 'runs' / '*' / 'manifest.json')]}
        self.runtime.mkdir()
        self.holder = parent.ParentLock(self.runtime / 'mail_worker.lock')  # stands in for a live worker
        self.addCleanup(lambda: self.holder.close())

    def check(self, **changes):
        write(self.config_path, dict(self.config, **changes))
        loop = parent.ParentLoop(self.world.root, 'np2611', prior_readback=self.world.prior,
                                 monitor_config=self.config_path)
        return loop.default_mail_check()

    def assert_not_ready(self, **changes):
        with self.assertRaises(parent.ParentStop) as raised:
            self.check(**changes)
        self.assertEqual(raised.exception.code, 'MAIL_PATH_NOT_READY')
        self.assertNotIn('artificial@example.invalid', json.dumps(raised.exception.evidence))

    def test_ready_mail_path_passes(self):
        self.check()

    def test_each_broken_part_is_refused(self):
        for changes in ({'mail_enabled': False}, {'mail_to': ''}, {'patterns': []},
                        {'patterns': [str(self.world.workspace / 'smoke' / '*' / 'manifest.json')]}):
            with self.subTest(changes=changes):
                self.assert_not_ready(**changes)

    def test_dead_worker_or_expired_sign_in_is_refused(self):
        write(self.runtime / 'outbox' / 'm1.json', {'state': 'auth_expired'})
        self.assert_not_ready()
        (self.runtime / 'outbox' / 'm1.json').unlink()
        self.holder.close()
        self.assert_not_ready()  # lock file exists but nobody holds it
        (self.runtime / 'mail_worker.lock').unlink()
        self.assert_not_ready()
        self.holder = parent.ParentLock(self.runtime / 'mail_worker.lock')

    def test_gmail_smtp_needs_a_sender_and_a_saved_password(self):
        smtp = {'mail_provider': 'gmail_smtp', 'mail_sender': 'artificial.sender@example.invalid'}
        self.assert_not_ready(**smtp)  # no smtp_secret.bin yet
        (self.runtime / 'smtp_secret.bin').write_bytes(b'artificial')
        self.assertEqual(self.check(**smtp)['mail_path'], 'ready')
        self.assert_not_ready(**dict(smtp, mail_sender=''))

    def test_failed_or_long_retrying_notices_are_refused_and_uncertain_is_only_reported(self):
        outbox = self.runtime / 'outbox'
        write(outbox / 'm1.json', {'state': 'failed_preserved', 'unsent_confirmed': True})
        self.assert_not_ready()
        (outbox / 'm1.json').unlink()
        write(outbox / 'm2.json', {'state': 'queued', 'attempts': 3})
        self.assert_not_ready()
        write(outbox / 'm2.json', {'state': 'queued', 'attempts': 2})
        write(outbox / 'm3.json', {'state': 'uncertain_preserved'})
        write(outbox / 'm4.json', {'state': 'accepted'})
        self.assertEqual(self.check(), {'mail_path': 'ready', 'uncertain_preserved': 1})


class Preflight(Harness):
    """`preflight` checks the start conditions of `run` and changes nothing."""

    def snapshot(self):
        return sorted((str(p.relative_to(self.world.root)), p.stat().st_size)
                      for p in self.world.root.rglob('*') if p.is_file())

    def test_ready_world_is_ready_and_nothing_is_written_or_called(self):
        before = self.snapshot()
        result = self.loop().preflight()
        self.assertTrue(result['ready'], result)
        self.assertEqual(result['checks']['ledger'], {'ok': True, 'recorded_cells': 1, 'total_cells': 4,
                                                      'prior_readback': str(self.world.prior.resolve()),
                                                      'next_run_id': 'np261102'})
        self.assertEqual(result['checks']['settings'], {'ok': True, 'stored': False})
        self.assertEqual(self.snapshot(), before)  # settings are not stored by a preflight
        self.assertEqual((self.world.calls, self.events), ([], []))

    def test_iteration_prechecks_of_run_are_also_checked(self):
        bad = self.world.root / 'bad_readback.json'
        write(bad, {'status': 'INVALID'})
        self.assertEqual(self.loop(prior=bad).preflight()['checks']['ledger']['code'], 'PRIOR_READBACK_INVALID')
        (self.world.workspace / 'runs' / 'np261102').mkdir(parents=True)
        self.assertEqual(self.loop().preflight()['checks']['ledger']['code'], 'RUN_ID_IN_USE')
        self.assertTrue(self.loop(prefix='np2612').preflight()['ready'])
        self.assertEqual(self.loop(prefix='bad prefix!').preflight()['checks']['ledger']['code'], 'USAGE_ERROR')

    def test_checkpoint_and_settings_follow_run(self):
        path = self.world.root / 'settings.json'
        write(path, {'schema': parent.SETTINGS_SCHEMA, 'checkpoint_recorded_counts': [1]})
        self.assertEqual(self.loop(settings=path).preflight()['checks']['ledger']['code'], 'CHECKPOINT_REACHED')
        self.assertEqual(self.loop(settings=path).run(), parent.EXIT_STOPPED)  # run agrees, and stores settings
        self.assertEqual(self.loop().preflight()['checks']['settings']['code'], 'USAGE_ERROR')  # differ from stored

    def test_each_failing_condition_is_named(self):
        self.monitor_ok = False
        self.mail_ok = False
        result = self.loop().preflight()
        self.assertFalse(result['ready'])
        self.assertEqual(result['checks']['monitor']['code'], 'MONITOR_NOT_PROVEN')
        self.assertEqual(result['checks']['mail_path']['code'], 'MAIL_PATH_NOT_READY')
        self.assertTrue(result['checks']['ledger']['ok'])
        self.assertEqual(self.events, [])

    def test_unacknowledged_stop_interrupted_parent_and_missing_readback_are_not_ready(self):
        write(self.directory() / 'stops' / 's1.json', {'stop_id': 's1', 'code': 'X'})
        write(self.directory() / 'parent_state.json', {'phase': 'sequence_running'})
        result = self.loop(prior=None).preflight()
        self.assertFalse(result['ready'])
        self.assertEqual(result['checks']['stops'], {'ok': False, 'unacknowledged': ['s1']})
        self.assertEqual(result['checks']['previous_parent'], {'ok': False, 'phase': 'sequence_running'})
        self.assertEqual(result['checks']['ledger']['code'], 'USAGE_ERROR')

    def test_held_parent_lock_is_not_ready(self):
        self.directory().mkdir(parents=True)
        holder = parent.ParentLock(self.directory() / 'parent.lock')
        try:
            self.assertEqual(self.loop().preflight()['checks']['parent_lock'],
                             {'ok': False, 'code': 'ANOTHER_PARENT_RUNNING'})
        finally:
            holder.close()
        self.assertTrue(self.loop().preflight()['ready'])


class DefaultRunnerRecordsChild(unittest.TestCase):
    """Review D1: the child PID and creation time are kept in parent_state (record only)."""

    def test_child_identity_is_saved_before_waiting(self):
        with tempfile.TemporaryDirectory() as temp:
            world = FakeWorld(temp)
            seen = []
            def probe(pid):
                seen.append(pid)
                return {'state': 'alive', 'pid': pid, 'created': 123}
            loop = parent.ParentLoop(world.root, 'np2611', prior_readback=world.prior, probe=probe)
            loop.iteration = {'steps_done': []}
            out, err = Path(temp) / 'o.log', Path(temp) / 'e.log'
            self.assertEqual(loop.default_runner([sys.executable, '-c', 'pass'], out, err, temp), 0)
            state = json.loads((loop.directory / 'parent_state.json').read_text(encoding='utf-8'))
            self.assertEqual(state['iteration']['child']['pid'], seen[0])
            self.assertEqual(state['iteration']['child']['created'], 123)


if __name__ == '__main__':
    unittest.main()
