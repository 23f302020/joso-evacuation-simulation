"""Independent-review fixes in watch.py (A1b, A5, A6, A8, A10): single enqueuer, core-only completion,
busy-file retry, visible mail trouble, no flood of old events."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import watch

CORE = {'status': 'COMPLETED', 'historical': False, 'purpose': 'core'}


def target(name, **extra):
    return {**CORE, 'target_id': name, 'source': 'D:/ws/runs/' + name + '/manifest.json', **extra}


class SingleEnqueuer(unittest.TestCase):
    def test_monitor_tick_does_not_enqueue_mail(self):
        with tempfile.TemporaryDirectory() as temp:
            dispatcher = watch.Dispatcher({'mail_enabled': True, 'diagnostics_enabled': False}, Path(temp))
            (Path(temp) / 'events').mkdir()
            with mock.patch.object(watch, 'sync_mail_outbox') as sync:
                dispatcher.tick(1000.0)
            sync.assert_not_called()


class CoreOnly(unittest.TestCase):
    def evidence(self, expected, *targets):
        return watch.all_complete_evidence({'expected_completed_targets': expected},
                                           {'targets': {str(i): t for i, t in enumerate(targets)}})

    def test_smoke_technical_suite_and_native_builds_are_not_counted(self):
        extras = (target('s', purpose='smoke', source='D:/ws/smoke/s/manifest.json'),
                  target('t', purpose='technical_fixture_suite', source='D:/ws/technical/t/manifest.json'),
                  {'status': 'COMPILED_VERSION_CHECKED_NOT_SIMULATED', 'historical': False, 'purpose': None,
                   'source': 'D:/native/build_state.json'})
        self.assertIsNone(self.evidence(2, target('a'), *extras))
        self.assertIsNotNone(self.evidence(2, target('a'), target('b'), *extras))

    def test_core_manifest_outside_runs_is_not_counted(self):
        self.assertIsNone(self.evidence(1, target('a', source='D:/ws/elsewhere/a/manifest.json')))

    def test_failed_cores_are_reported_but_other_failures_are_not(self):
        failed_core = {'status': 'FAILED', 'historical': False, 'purpose': 'core',
                       'source': 'D:/ws/runs/x/manifest.json'}
        failed_smoke = {'status': 'FAILED', 'historical': False, 'purpose': 'smoke',
                        'source': 'D:/ws/smoke/y/manifest.json'}
        status = self.evidence(1, target('a'), failed_core, failed_smoke)['status']
        self.assertIn('失敗保全1', status)

    def test_a_changed_expectation_produces_a_new_event(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            state = {'targets': {'a': target('a'), 'b': target('b')}}
            watch.detect_all_complete({'expected_completed_targets': 1}, runtime, state)
            watch.detect_all_complete({'expected_completed_targets': 1}, runtime, state)
            self.assertEqual(len(list((runtime / 'events').glob('*.json'))), 1)
            watch.detect_all_complete({'expected_completed_targets': 2}, runtime, state)
            self.assertEqual(len(list((runtime / 'events').glob('*.json'))), 2)


class BusyFile(unittest.TestCase):
    def test_atomic_json_retries_when_another_process_holds_the_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'x.json'
            real, calls = watch.os.replace, []

            def flaky(src, dst):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError(5, 'busy')
                return real(src, dst)

            with mock.patch.object(watch.os, 'replace', flaky), mock.patch.object(watch.time, 'sleep'):
                watch.atomic_json(path, {'a': 1})
            self.assertEqual(watch.read_json(path), {'a': 1})
            self.assertEqual(len(calls), 3)
            self.assertEqual(list(Path(temp).glob('*.tmp')), [])

    def test_atomic_json_gives_up_cleanly_after_many_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'x.json'
            with mock.patch.object(watch.os, 'replace', side_effect=PermissionError(5, 'busy')), \
                    mock.patch.object(watch.time, 'sleep'):
                with self.assertRaises(PermissionError):
                    watch.atomic_json(path, {'a': 1})
            self.assertEqual(list(Path(temp).glob('*.tmp')), [])

    def test_sync_skips_events_already_queued_and_contains_unreadable_events(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            events, outbox = runtime / 'events', runtime / 'outbox'
            events.mkdir()
            outbox.mkdir()
            (events / 'queued.json').write_text('{not json', encoding='utf-8')
            (outbox / 'queued.json').write_text('{}', encoding='utf-8')
            (events / 'broken.json').write_text('{not json', encoding='utf-8')
            self.assertEqual(watch.sync_mail_outbox({'mail_enabled': True}, runtime), 0)


class OldEvents(unittest.TestCase):
    def test_mail_enabled_since_skips_older_events(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            watch.save_event(runtime / 'events', 't-old', 'failed', {'target_id': 'old', 'source': 's'},
                             ai_diagnostics=False)
            path = next((runtime / 'events').glob('*.json'))
            event = watch.read_json(path)
            event['at_utc'] = '2026-01-01T00:00:00+00:00'
            watch.atomic_json(path, event)
            watch.save_event(runtime / 'events', 't-new', 'failed', {'target_id': 'new', 'source': 's'},
                             ai_diagnostics=False)
            config = {'mail_enabled': True, 'mail_enabled_since': '2026-06-01T00:00:00+00:00'}
            self.assertEqual(watch.sync_mail_outbox(config, runtime), 1)


class MailTroubleVisible(unittest.TestCase):
    def outbox_with(self, runtime, name, state):
        (runtime / 'outbox').mkdir(parents=True, exist_ok=True)
        watch.atomic_json(runtime / 'outbox' / (name + '.json'),
                          {'schema': 'simulation_watch_mail_v1', 'id': name, 'state': state})

    def test_counts_by_state(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            for name, state in (('a', 'queued'), ('b', 'queued'), ('c', 'auth_expired')):
                self.outbox_with(runtime, name, state)
            self.assertEqual(watch.mail_counts(runtime), {'queued': 2, 'auth_expired': 1})
        self.assertEqual(watch.mail_counts(Path(tempfile.gettempdir()) / 'no-such-runtime-dir'), {})

    def test_trouble_states_raise_one_local_event_each_and_never_mail(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            self.outbox_with(runtime, 'a', 'auth_expired')
            self.outbox_with(runtime, 'b', 'uncertain_preserved')
            self.outbox_with(runtime, 'c', 'accepted')
            dispatcher = watch.Dispatcher({'diagnostics_enabled': False}, runtime)
            with mock.patch.object(watch, 'notify', return_value='submitted'):
                dispatcher.tick(1000.0)
                dispatcher.tick(1001.0)
            kinds = sorted(watch.read_json(p)['kind'] for p in (runtime / 'events').glob('*.json'))
            self.assertEqual(kinds, ['mail_auth_expired', 'mail_uncertain_preserved'])
            self.assertFalse(any(watch.mail_worthy(k) for k in kinds))

    def test_inbox_page_shows_mail_trouble(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            (runtime / 'events').mkdir()
            self.outbox_with(runtime, 'a', 'auth_expired')
            watch.render_status(runtime, {})
            self.assertIn('auth_expired', (runtime / 'status.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
