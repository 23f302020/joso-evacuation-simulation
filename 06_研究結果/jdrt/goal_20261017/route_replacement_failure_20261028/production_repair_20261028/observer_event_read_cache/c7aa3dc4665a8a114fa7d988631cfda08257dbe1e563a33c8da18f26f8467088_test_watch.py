import json
import tempfile
import unittest
import os
import subprocess
import sys
import time
import hashlib
from unittest.mock import patch, Mock
from pathlib import Path

import watch


class FixtureCommandBinding(unittest.TestCase):
    def fixture(self, root, pid=123):
        factory = root / 'technical/suite/factory.py'
        factory.parent.mkdir(parents=True)
        factory.write_text("CASES = ('first', 'second')\n", encoding='utf-8')
        parent = factory.with_name('manifest.json')
        watch.atomic_json(parent, {'protocol': 'realtime_choice_fixture_suite_v1',
            'purpose': 'technical_fixture_suite', 'run_id': 'suite', 'pid': pid,
            'status': 'RUNNING', 'research_adoption_permitted': False,
            'factory_sha256': hashlib.sha256(factory.read_bytes()).hexdigest()})
        inputs = root / 'technical/suite_c01/fixture_inputs/manifest.json'
        watch.atomic_json(inputs, {'protocol': 'realtime_choice_fixture_v1', 'fixture_case': 'first',
            'research_adoption_permitted': False,
            'source_sha256': {'04_プログラム/scripts/jdrt_choice_fixtures.py': watch.read_json(parent)['factory_sha256']}})
        child = root / 'technical/suite_c01/execution/manifest.json'
        watch.atomic_json(child, {'protocol': 'realtime_choice_fixture_v1', 'purpose': 'fixture',
            'run_id': 'suite_c01', 'pid': pid, 'status': 'RUNNING', 'fixture_case': 'first',
            'research_adoption_permitted': False,
            'input_manifest_sha256': hashlib.sha256(inputs.read_bytes()).hexdigest()})
        return child, parent, factory, inputs

    def test_verified_suite_command_is_bound_to_child_without_source_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            child, parent, factory, inputs = self.fixture(Path(folder))
            before = {p: p.read_bytes() for p in (child, parent, factory, inputs)}
            called = []
            def match(pid, target):
                called.append((pid, target))
                return target == 'suite'
            value = watch.snapshot(child, {}, 1, lambda _: {'state': 'alive', 'created': 100}, match)
            self.assertEqual(value['flags'], [])
            self.assertEqual(called, [(123, 'suite')])
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_wrong_parent_factory_input_or_case_does_not_gain_suite_identity(self):
        for change in ('parent_pid', 'parent_protocol', 'parent_status', 'factory_sha',
                       'input_sha', 'case', 'path_identity', 'missing_parent'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                child, parent, factory, inputs = self.fixture(Path(folder))
                c, p = watch.read_json(child), watch.read_json(parent)
                if change == 'parent_pid': p['pid'] = 999
                elif change == 'parent_protocol': p['protocol'] = 'unrelated'
                elif change == 'parent_status': p['status'] = 'FAILED'
                elif change == 'factory_sha': factory.write_text("CASES = ('forged',)\n")
                elif change == 'input_sha': c['input_manifest_sha256'] = 'wrong'
                elif change == 'case': c['fixture_case'] = 'second'
                elif change == 'path_identity': c['run_id'] = 'other_c01'
                watch.atomic_json(parent, p); watch.atomic_json(child, c)
                if change == 'missing_parent': parent.unlink()
                value = watch.snapshot(child, {}, 1, lambda _: {'state': 'alive', 'created': 100},
                                       lambda pid, target: target == 'suite')
                self.assertIn('process_command_mismatch', value['flags'])

    def test_created_pid_without_successful_command_proof_is_rechecked(self):
        with tempfile.TemporaryDirectory() as folder:
            child, *_ = self.fixture(Path(folder))
            match = unittest.mock.Mock(return_value=False)
            old = {'pid': 123, 'process': {'state': 'alive', 'created': 100}}
            value = watch.snapshot(child, old, 1, lambda _: {'state': 'alive', 'created': 100}, match)
            match.assert_called_once()
            self.assertIn('process_command_mismatch', value['flags'])

    def test_same_pid_cannot_cache_a_changed_parent_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            child, parent, *_ = self.fixture(Path(folder))
            probe = lambda _: {'state': 'alive', 'created': 100}
            old = watch.snapshot(child, {}, 1, probe, lambda *args: True)
            p = watch.read_json(parent); p['pid'] = 999; watch.atomic_json(parent, p)
            current = watch.snapshot(child, old, 2, probe, lambda pid, target: target == 'suite')
            self.assertIn('process_command_mismatch', current['flags'])

    def test_command_match_uses_exact_windows_arguments(self):
        command = subprocess.list2cmdline(['C:/Program Files/Python/python.exe', '-c', 'pass', '--run-id', 'suite'])
        response = subprocess.CompletedProcess([], 0, json.dumps(command).encode(), b'')
        with patch.object(watch.subprocess, 'run', return_value=response):
            self.assertTrue(watch.command_matches(123, 'suite'))
            for wrong in ('suit', 'suite_c01', 'Program', ''):
                self.assertFalse(watch.command_matches(123, wrong))

    def test_real_windows_suite_command_and_child_manifest(self):
        if os.name != 'nt': self.skipTest('Windows integration')
        with tempfile.TemporaryDirectory() as folder:
            process = subprocess.Popen([sys._base_executable, '-B', '-c', 'import time; time.sleep(20)', '--run-id', 'suite'])
            try:
                child, *_ = self.fixture(Path(folder), process.pid)
                value = watch.snapshot(child, {}, 1)
                self.assertEqual(value['process']['state'], 'alive')
                self.assertEqual(value['flags'], [])
            finally:
                process.terminate(); process.wait(timeout=5)

    def test_exit_during_command_lookup_keeps_grace_without_false_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            child, *_ = self.fixture(Path(folder))
            observed = iter([{'state': 'alive', 'created': 100}, {'state': 'absent'}])
            value = watch.snapshot(child, {}, 1, lambda _: next(observed), lambda *_: False)
            self.assertEqual(value['flags'], [])
            self.assertEqual(value['absent_since'], 1)
            self.assertNotIn('command_verified_binding', value)

    def test_pid_reused_during_command_lookup_cannot_gain_command_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            child, *_ = self.fixture(Path(folder))
            observed = iter([{'state': 'alive', 'created': 100}, {'state': 'alive', 'created': 200}])
            value = watch.snapshot(child, {}, 1, lambda _: next(observed), lambda *_: True)
            self.assertIn('process_identity_changed', value['flags'])
            self.assertNotIn('command_verified_binding', value)


class FixtureSuiteProgress(unittest.TestCase):
    def snapshots(self, first, second, purpose='technical_fixture_suite'):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'manifest.json'
            watch.atomic_json(source, {'protocol': 'realtime_choice_fixture_suite_v1',
                'purpose': purpose, 'run_id': 'suite', 'pid': 123, 'status': 'RUNNING'})
            progress = source.with_name('progress.json')
            probe = lambda _: {'state': 'alive', 'created': 100}
            watch.atomic_json(progress, first)
            old = watch.snapshot(source, {}, 10, probe, lambda *_: True)
            watch.atomic_json(progress, second)
            current = watch.snapshot(source, old, 71, probe, lambda *_: True)
            return old, current

    def test_completed_cases_advance_parent_progress_without_inventing_sim_time(self):
        old, current = self.snapshots({'completed_cases': 1}, {'completed_cases': 2})
        self.assertIsNone(current['sim_sec'])
        self.assertEqual(current['last_progress'], 71)
        self.assertNotIn('stalled', watch.classify(current, old, 71, 60))

    def test_suite_heartbeat_without_completed_case_remains_stalled(self):
        old, current = self.snapshots({'completed_cases': 1, 'at_jst': 'before'},
                                      {'completed_cases': 1, 'at_jst': 'after'})
        self.assertIn('stalled', watch.classify(current, old, 71, 60))

    def test_core_clock_still_overrides_unrelated_case_counter(self):
        old, current = self.snapshots({'time_sec': 10, 'completed_cases': 1},
                                      {'time_sec': 10, 'completed_cases': 2}, purpose='core')
        self.assertEqual(current['sim_sec'], 10)
        self.assertIn('stalled', watch.classify(current, old, 71, 60))

    def test_noninteger_suite_counter_cannot_create_progress(self):
        old, current = self.snapshots({'completed_cases': 'one'}, {'completed_cases': True})
        self.assertIn('stalled', watch.classify(current, old, 71, 60))


class ExecutionTiming(unittest.TestCase):
    def test_manifest_times_are_normalized_and_saved_with_event(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'manifest.json'
            data = {'run_id': 'clock-fixture', 'status': 'COMPLETED',
                    'started_at_jst': '2026-01-01T09:00:00.250000+09:00',
                    'finished_at_jst': '2026-01-01T00:01:02.750000Z'}
            watch.atomic_json(source, data)
            original = source.read_bytes()
            value = watch.snapshot(source, {}, 1)
            timing = value['execution_timing']
            self.assertEqual(timing['started_at_utc'], '2026-01-01T00:00:00.250000+00:00')
            self.assertEqual(timing['finished_at_utc'], '2026-01-01T00:01:02.750000+00:00')
            self.assertEqual(timing['elapsed_sec'], 62.5)
            self.assertEqual(timing['status'], 'complete')
            self.assertEqual(timing['start_source'], 'started_at_jst')
            self.assertEqual(timing['finish_source'], 'finished_at_jst')
            event = watch.save_event(root / 'events', str(source), 'completed', value)
            self.assertEqual(watch.read_json(event)['evidence']['execution_timing'], timing)
            saved = event.read_bytes()
            watch.save_event(root / 'events', str(source), 'completed', {})
            self.assertEqual(event.read_bytes(), saved)
            self.assertEqual(source.read_bytes(), original)
            watch.render_status(root, {'targets': {}, 'observed_epoch': 1})
            html = (root / 'status.html').read_text(encoding='utf-8')
            self.assertIn('2026-01-01 09:00:00.250000+09:00', html)
            self.assertIn('2026-01-01 09:01:02.750000+09:00', html)
            self.assertIn('1分2.500秒', html)

    def test_missing_invalid_reversed_and_running_times_are_not_guessed(self):
        cases = [
            ({}, 'missing', None),
            ({'started_at_jst': 'bad', 'finished_at_jst': '2026-01-01T00:00:00Z'}, 'invalid', None),
            ({'started_at_jst': '2026-01-01T00:00:00', 'finished_at_jst': '2026-01-01T00:00:00Z'}, 'invalid', None),
            ({'started_at_jst': '2026-01-02T00:00:00Z', 'finished_at_jst': '2026-01-01T00:00:00Z'}, 'reversed', None),
            ({'started_at_utc': '2026-01-01T00:00:00Z', 'finished_at_utc': '2026-01-01T00:00:00Z'}, 'complete', 0),
        ]
        for fields, status, elapsed in cases:
            with self.subTest(fields=fields):
                timing = watch.execution_timing({'status': 'FAILED', **fields})
                self.assertEqual(timing['status'], status)
                self.assertEqual(timing['elapsed_sec'], elapsed)
        timing = watch.execution_timing({'status': 'RUNNING',
            'started_at_jst': '2026-01-01T00:00:00Z', 'finished_at_jst': '2026-01-02T00:00:00Z'})
        self.assertEqual(timing['status'], 'running')
        self.assertIsNone(timing['elapsed_sec'])
        self.assertIsNone(timing['finished_at_utc'])

    def test_legacy_event_displays_unknown_without_changing_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            event = watch.save_event(root / 'events', 'legacy', 'completed', {})
            original = event.read_bytes()
            watch.render_status(root, {'targets': {}, 'observed_epoch': 1})
            self.assertIn('所要時間：不明', (root / 'status.html').read_text(encoding='utf-8'))
            self.assertEqual(event.read_bytes(), original)


class Contracts(unittest.TestCase):
    def test_read_failure_records_exception_without_losing_previous_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'manifest.json'
            source.write_text('{}', encoding='utf-8')
            runtime = root / 'runtime'
            state = {'initialized': True, 'targets': {str(source):
                     {'status': 'RUNNING', 'target_id': 'artificial', 'pid': 123}}}
            config = {'patterns': [str(source)], 'stale_sec': 600}
            with patch.object(watch, 'snapshot', side_effect=FileNotFoundError('Artificial missing executable')):
                for now in (1, 2, 3):
                    watch.observe(config, runtime, state, now, lambda _: {'state': 'alive'})
            recorded = state['targets'][str(source)]
            self.assertEqual(recorded['status'], 'RUNNING')
            self.assertEqual(recorded['pid'], 123)
            self.assertEqual(recorded['read_failures'], 3)
            self.assertEqual(recorded['read_error_type'], 'FileNotFoundError')
            self.assertEqual(recorded['read_error'], 'Artificial missing executable')
            events = list((runtime / 'events').glob('*.json'))
            self.assertEqual(len(events), 1)
            self.assertEqual(watch.read_json(events[0])['evidence']['read_error_type'], 'FileNotFoundError')

    def limited_dispatcher(self, root):
        events = root / 'events'
        events.mkdir()
        for number in range(3):
            watch.atomic_json(events / ('r' + str(number) + '.json'), {
                'delivery': 'done', 'notification': 'submitted', 'delivery_started_epoch': 10000})
        watch.atomic_json(events / 'a.json', {'delivery': 'pending', 'notification': 'submitted'})
        for name in ('b', 'c'):
            watch.atomic_json(events / (name + '.json'), {'delivery': 'pending', 'notification': 'pending'})
        config = {'diagnostics_enabled': True, 'max_diagnostics_per_hour': 3,
                  'diagnostic_timeout_sec': 180, 'notifications_enabled': True}
        return watch.Dispatcher(config, root)

    def test_notifications_progress_one_per_tick_at_diagnostic_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dispatcher = self.limited_dispatcher(root)
            with patch.object(watch, 'notify', return_value='submitted') as notify, \
                    patch.object(watch.subprocess, 'Popen') as launch:
                dispatcher.tick(10001)
                self.assertEqual(watch.read_json(root / 'events/b.json')['notification'], 'submitted')
                self.assertEqual(watch.read_json(root / 'events/c.json')['notification'], 'pending')
                self.assertEqual(notify.call_count, 1)
                dispatcher.tick(10002)
                self.assertEqual(watch.read_json(root / 'events/c.json')['notification'], 'submitted')
                self.assertEqual(notify.call_count, 2)
                launch.assert_not_called()
            self.assertEqual(watch.read_json(root / 'events/a.json')['delivery'], 'pending')

    def test_notification_progresses_while_diagnostic_child_is_running(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dispatcher = self.limited_dispatcher(root)
            child = Mock()
            child.poll.return_value = None
            running = (child, root / 'events/a.json', 10000, Mock(), Mock())
            dispatcher.child = running
            with patch.object(watch, 'notify', return_value='submitted'), \
                    patch.object(watch.subprocess, 'Popen') as launch:
                dispatcher.tick(10001)
                self.assertEqual(watch.read_json(root / 'events/b.json')['notification'], 'submitted')
                self.assertIs(dispatcher.child, running)
                child.kill.assert_not_called()
                launch.assert_not_called()

    def test_disabled_notification_is_persisted_despite_diagnostic_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dispatcher = self.limited_dispatcher(root)
            dispatcher.config['notifications_enabled'] = False
            with patch.object(watch, 'notify') as notify, \
                    patch.object(watch.subprocess, 'Popen') as launch:
                dispatcher.tick(10001)
                self.assertEqual(watch.read_json(root / 'events/b.json')['notification'], 'disabled')
                notify.assert_not_called()
                launch.assert_not_called()

    def test_terminal_requires_validation(self):
        self.assertEqual(watch.classify({'status': 'COMPLETED', 'flags': []}, {}, 10, 60), ['completed'])

    def test_error_and_orphan(self):
        for status, flags, expected in [('FAILED', [], 'failed'), ('RUNNING', ['process_absent'], 'process_absent')]:
            with self.subTest(status=status):
                self.assertIn(expected, watch.classify({'status': status, 'flags': flags}, {}, 10, 60))

    def test_stall_and_progress_reset(self):
        old = {'progress_token': '1', 'last_progress': 10}
        self.assertIn('stalled', watch.classify({'status': 'RUNNING', 'flags': [], 'progress_token': '1'}, old, 71, 60))
        self.assertNotIn('stalled', watch.classify({'status': 'RUNNING', 'flags': [], 'progress_token': '2'}, old, 71, 60))

    def test_repeated_event_retains_delivery_state(self):
        with tempfile.TemporaryDirectory() as folder:
            first = watch.save_event(Path(folder), 'run/path', 'completed', {'status': 'COMPLETED'})
            data = json.loads(first.read_text(encoding='utf-8'))
            data['delivery'] = 'done'
            watch.atomic_json(first, data)
            second = watch.save_event(Path(folder), 'run/path', 'completed', {'status': 'COMPLETED'})
            self.assertEqual(first, second)
            self.assertEqual(json.loads(second.read_text(encoding='utf-8'))['delivery'], 'done')

    def test_unknown_status_never_completed(self):
        self.assertEqual(watch.classify({'status': 'SURPRISE', 'flags': []}, {}, 0, 60), ['unknown_status'])

    def test_fixture_success_is_archived_without_ai_but_failure_is_actionable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            success = watch.save_event(root, 'fixture', 'completed', {'purpose': 'fixture'})
            failure = watch.save_event(root, 'fixture', 'failed', {'purpose': 'fixture'})
            parent = watch.save_event(root, 'suite', 'completed', {'purpose': 'technical_fixture_suite'})
            self.assertEqual(watch.read_json(success)['delivery'], 'not_required')
            self.assertEqual(watch.read_json(success)['notification'], 'not_required')
            self.assertEqual(watch.read_json(failure)['delivery'], 'pending')
            self.assertEqual(watch.read_json(parent)['delivery'], 'pending')

    def test_baseline_restart_and_new_terminal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'old' / 'manifest.json'
            watch.atomic_json(source, {'status': 'FAILED', 'run_id': 'old'})
            config = {'patterns': [str(root / '*' / 'manifest.json')], 'stale_sec': 60}
            runtime = root / 'runtime'
            state = {}
            probe = lambda pid: {'state': 'alive', 'created': 1, 'pid': pid}
            watch.observe(config, runtime, state, 1, probe)
            self.assertEqual(list((runtime / 'events').glob('*.json')), [])
            state = watch.read_json(runtime / 'state.json')
            new = root / 'new' / 'manifest.json'
            watch.atomic_json(new, {'status': 'COMPLETED', 'run_id': 'new'})
            before = new.read_bytes()
            watch.observe(config, runtime, state, 2, probe)
            watch.observe(config, runtime, state, 3, probe)
            events = list((runtime / 'events').glob('*.json'))
            self.assertEqual(len(events), 1)
            self.assertEqual(watch.read_json(events[0])['kind'], 'completed')
            self.assertEqual(new.read_bytes(), before)

    def test_partial_json_grace_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'manifest.json'
            source.write_text('{', encoding='utf-8')
            config = {'patterns': [str(source)], 'stale_sec': 60}
            state = {}
            probe = lambda pid: {'state': 'alive'}
            for now in range(3):
                watch.observe(config, root / 'runtime', state, now, probe)
            events = list((root / 'runtime/events').glob('*.json'))
            self.assertEqual(watch.read_json(events[0])['kind'], 'unreadable_state')
            watch.atomic_json(source, {'status': 'COMPLETED', 'run_id': 'new'})
            watch.observe(config, root / 'runtime', state, 4, probe)
            self.assertEqual(len(list((root / 'runtime/events').glob('*.json'))), 2)

    def test_pid_reuse_and_exit_grace(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'manifest.json'
            watch.atomic_json(source, {'status': 'RUNNING', 'run_id': 'x', 'pid': 123})
            old = {'pid': 123, 'process': {'created': 100}}
            current = watch.snapshot(source, old, 10, lambda _: {'state': 'alive', 'created': 200})
            self.assertIn('process_identity_changed', current['flags'])
            current = watch.snapshot(source, {}, 10, lambda _: {'state': 'absent'})
            self.assertNotIn('process_absent', current['flags'])
            current = watch.snapshot(source, current, 14, lambda _: {'state': 'absent'})
            self.assertIn('process_absent', current['flags'])

    def test_partial_log_and_counter_alarm(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'manifest.json'
            watch.atomic_json(source, {'status': 'RUNNING', 'run_id': 'x', 'pid': 123})
            watch.atomic_json(root / 'progress.json', {'time_sec': 1, 'counts': {'collisions': 1}})
            log = root / 'sumo_errors.log'
            log.write_bytes(b'Err')
            probe = lambda _: {'state': 'alive', 'created': 1}
            old = watch.snapshot(source, {}, 10, probe, lambda *_: True)
            self.assertIn('nonzero_collisions', old['flags'])
            with log.open('ab') as stream:
                stream.write(b'or: artificial test\n')
            current = watch.snapshot(source, old, 11, probe)
            self.assertIn('log_error', current['flags'])
            self.assertNotIn('log_error', watch.snapshot(source, current, 12, probe)['flags'])

    def test_heartbeat_cannot_hide_frozen_simulation_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'manifest.json'
            watch.atomic_json(source, {'status': 'RUNNING', 'run_id': 'x', 'pid': 123})
            watch.atomic_json(root / 'progress.json', {'time_sec': 1, 'at_jst': 'first'})
            probe = lambda _: {'state': 'alive', 'created': 1}
            old = watch.snapshot(source, {}, 10, probe, lambda *_: True)
            watch.atomic_json(root / 'progress.json', {'time_sec': 1, 'at_jst': 'later'})
            current = watch.snapshot(source, old, 71, probe)
            self.assertIn('stalled', watch.classify(current, old, 71, 60))

    def test_historical_path_reuse_is_observed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'manifest.json'
            config = {'patterns': [str(source)], 'stale_sec': 60}
            state = {}
            probe = lambda pid: {'state': 'alive', 'created': 1, 'pid': pid}
            watch.atomic_json(source, {'status': 'COMPLETED', 'run_id': 'old'})
            watch.observe(config, root / 'runtime', state, 1, probe)
            watch.atomic_json(source, {'status': 'COMPLETED', 'run_id': 'new'})
            watch.observe(config, root / 'runtime', state, 2, probe)
            kinds = [watch.read_json(p)['kind'] for p in (root / 'runtime/events').glob('*.json')]
            self.assertIn('target_identity_changed', kinds)
            self.assertIn('completed', kinds)

    def test_dashboard_escapes_untrusted_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            watch.save_event(root / 'events', '<script>bad</script>', 'failed', {})
            watch.render_status(root, {'targets': {}, 'observed_epoch': 1})
            content = (root / 'status.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>bad</script>', content)
            self.assertIn('&lt;script&gt;bad&lt;/script&gt;', content)

    def test_failed_dispatch_is_preserved_and_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            event = watch.save_event(root / 'events', 'test', 'failed', {})
            config = {'diagnostics_enabled': True, 'max_diagnostics_per_hour': 3,
                      'diagnostic_timeout_sec': 30, 'codex_exe': 'missing.exe', 'model': 'test', 'runtime': str(root)}
            dispatcher = watch.Dispatcher(config, root)
            with patch.object(watch, 'notify', return_value='submitted'), patch.object(watch.subprocess, 'Popen', side_effect=OSError) as launch:
                dispatcher.tick(10000)
                dispatcher.tick(10001)
            self.assertEqual(launch.call_count, 1)
            self.assertEqual(watch.read_json(event)['delivery'], 'failed_preserved')

    def test_diagnostic_output_is_absolute_and_context_is_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            command = watch.diagnostic_command({'runtime': folder, 'codex_exe': 'codex.exe', 'model': 'test'}, Path('relative.reply'))
            self.assertTrue(Path(command[command.index('-o') + 1]).is_absolute())
            self.assertEqual(Path(command[command.index('-C') + 1]), Path(folder) / 'diagnostic_context')
            self.assertIn('--ignore-user-config', command)

    def test_hourly_limit_preserves_pending_events(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for number in range(4):
                watch.save_event(root / 'events', str(number), 'failed', {})
            config = {'diagnostics_enabled': True, 'max_diagnostics_per_hour': 3,
                      'diagnostic_timeout_sec': 30, 'codex_exe': 'missing.exe', 'model': 'test',
                      'runtime': str(root), 'notifications_enabled': False}
            dispatcher = watch.Dispatcher(config, root)
            with patch.object(watch.subprocess, 'Popen', side_effect=OSError) as launch:
                for number in range(5):
                    dispatcher.tick(10000 + number)
            self.assertEqual(launch.call_count, 3)
            self.assertEqual(sum(watch.read_json(p)['delivery'] == 'pending' for p in (root / 'events').glob('*.json')), 1)

    def test_observation_gap_during_active_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = {'initialized': True, 'observed_epoch': 1, 'targets': {'gone': {'status': 'RUNNING'}}}
            watch.observe({'patterns': [], 'stale_sec': 60}, root, state, 100, lambda _: {'state': 'alive'})
            events = [watch.read_json(p)['kind'] for p in (root / 'events').glob('*.json')]
            self.assertIn('monitoring_gap', events)
            self.assertIn('state_missing', events)

    def test_real_windows_process_exit_and_lock(self):
        if os.name != 'nt':
            self.skipTest('Windows integration')
        with tempfile.TemporaryDirectory() as folder:
            lock = watch.Exclusive(Path(folder) / 'lock')
            with self.assertRaises(RuntimeError):
                watch.Exclusive(Path(folder) / 'lock')
            lock.close()
            watch.Exclusive(Path(folder) / 'lock').close()
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
            try:
                identity = watch.process_identity(child.pid)
                self.assertEqual(identity['state'], 'alive')
                self.assertGreater(identity['created'], 0)
            finally:
                child.terminate()
                child.wait(timeout=5)
            self.assertEqual(watch.process_identity(child.pid)['state'], 'absent')

    def test_real_daemon_exit_event_and_restart_deduplication(self):
        if os.name != 'nt':
            self.skipTest('Windows integration')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = 'artificial_daemon_test'
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)', marker])
            source = root / 'manifest.json'
            runtime = root / 'runtime'
            watch.atomic_json(source, {'status': 'RUNNING', 'run_id': marker, 'pid': child.pid})
            config = {'runtime': str(runtime), 'patterns': [str(source)], 'sample_sec': 10,
                      'stale_sec': 600, 'diagnostics_enabled': False, 'notifications_enabled': False}
            config_path = root / 'config.json'
            watch.atomic_json(config_path, config)
            # Windows venv launchers spawn a second Python PID; use the base runtime
            # for this owned test process so Popen termination covers the actual observer.
            command = [sys._base_executable, '-B', str(watch.BASE / 'watch.py'), 'run', '--config', str(config_path)]
            daemon = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                child.wait(timeout=10)
                watch.atomic_json(source, {'status': 'COMPLETED', 'run_id': marker, 'pid': child.pid})
                began = time.time()
                while not list((runtime / 'events').glob('*.json')) and time.time() - began < 8:
                    time.sleep(.1)
                events = list((runtime / 'events').glob('*.json'))
                self.assertEqual(len(events), 1)
                self.assertEqual(watch.read_json(events[0])['kind'], 'completed')
                self.assertLess(time.time() - began, 5)  # one-second exit check, not ten-second discovery
                daemon.terminate()
                daemon.communicate(timeout=10)
                daemon = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                deadline = time.time() + 10
                while time.time() < deadline:
                    if watch.read_json(runtime / 'state.json')['monitor_pid'] == daemon.pid:
                        break
                    time.sleep(.1)
                self.assertEqual(watch.read_json(runtime / 'state.json')['monitor_pid'], daemon.pid)
                self.assertEqual(len(list((runtime / 'events').glob('*.json'))), 1)
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=10)
                if daemon.poll() is None:
                    daemon.terminate()
                daemon.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
