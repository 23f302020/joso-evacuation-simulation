"""AI-less configuration contract (school PC): no AI process, no stale pending delivery."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import configure
import watch


class ConfigureWithoutAi(unittest.TestCase):
    def run_configure(self, *argv):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            with patch.object(configure, 'BASE', base), patch.object(sys, 'argv', ['configure.py', *argv]):
                configure.main()
            return json.loads((base / 'config.json').read_text(encoding='utf-8'))

    def test_no_ai_config_needs_no_codex_and_disables_diagnostics(self):
        config = self.run_configure('--no-ai')
        self.assertIs(config['diagnostics_enabled'], False)
        for key in ('codex_exe', 'model', 'diagnostic_timeout_sec', 'max_diagnostics_per_hour'):
            self.assertNotIn(key, config)

    def test_codex_path_is_still_required_without_no_ai(self):
        with tempfile.TemporaryDirectory() as name:
            with patch.object(configure, 'BASE', Path(name)), patch.object(sys, 'argv', ['configure.py']):
                with self.assertRaises(SystemExit):
                    configure.main()

    def test_no_ai_and_codex_path_together_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            with patch.object(configure, 'BASE', Path(name)), \
                    patch.object(sys, 'argv', ['configure.py', '--no-ai', '--codex-exe', sys.executable]):
                with self.assertRaises(SystemExit):
                    configure.main()


class NoAiDispatch(unittest.TestCase):
    def test_event_without_ai_has_no_pending_delivery(self):
        with tempfile.TemporaryDirectory() as name:
            path = watch.save_event(Path(name), 'run/a', 'failed', {}, ai_diagnostics=False)
            event = watch.read_json(path)
            self.assertEqual(event['delivery'], 'not_applicable')
            self.assertEqual(event['notification'], 'pending')

    def test_event_with_ai_keeps_pending_delivery(self):
        with tempfile.TemporaryDirectory() as name:
            self.assertEqual(watch.read_json(watch.save_event(Path(name), 'run/a', 'failed', {}))['delivery'], 'pending')

    def test_fixture_success_stays_not_required_without_ai(self):
        with tempfile.TemporaryDirectory() as name:
            path = watch.save_event(Path(name), 'f', 'completed', {'purpose': 'fixture'}, ai_diagnostics=False)
            self.assertEqual(watch.read_json(path)['delivery'], 'not_required')

    def test_pending_events_never_start_a_process_when_diagnostics_off_or_absent(self):
        for config in ({'diagnostics_enabled': False, 'notifications_enabled': False},
                       {'notifications_enabled': False}):
            with tempfile.TemporaryDirectory() as name:
                root = Path(name)
                (root / 'events').mkdir()
                watch.atomic_json(root / 'events/a.json', {'delivery': 'pending', 'notification': 'pending'})
                dispatcher = watch.Dispatcher(config, root)
                with patch.object(watch.subprocess, 'Popen') as popen:
                    dispatcher.tick(1000)
                    dispatcher.tick(2000)
                popen.assert_not_called()
                self.assertEqual(watch.read_json(root / 'events/a.json')['delivery'], 'pending')


if __name__ == '__main__':
    unittest.main()
