"""smtp_mail.configure_mail: write the Gmail settings into config.json without hand editing.

Other keys are preserved, nothing secret is written, invalid input leaves the file untouched,
and an existing mail_enabled_since is kept unless a new one is given (the window never moves silently).
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import smtp_mail
import watch

SENDER, TO = 'sender.synthetic@gmail.com', 'to.synthetic@example.invalid'
NOW = datetime(2026, 11, 13, 1, 2, 3, tzinfo=timezone.utc)
BASE = {'schema': 'simulation_watch_config_v1', 'runtime': 'C:/x/runtime', 'patterns': ['C:/x/runs/*/manifest.json'],
        'sample_sec': 10, 'stale_sec': 600, 'diagnostics_enabled': False}


class Configure(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / 'config.json'
        watch.atomic_json(self.path, dict(BASE))

    def config(self):
        return watch.read_json(self.path)

    def test_sets_the_mail_keys_and_keeps_everything_else(self):
        smtp_mail.configure_mail(self.path, SENDER, TO, now=NOW)
        config = self.config()
        for key, value in BASE.items():
            self.assertEqual(config[key], value)
        self.assertEqual(config['mail_provider'], 'gmail_smtp')
        self.assertEqual(config['mail_sender'], SENDER)
        self.assertEqual(config['mail_to'], TO)
        self.assertEqual(config['mail_enabled_since'], '2026-11-13T01:02:03+00:00')
        self.assertNotIn('mail_enabled', config)  # enabling is a separate, explicit step

    def test_existing_window_is_kept_unless_a_new_one_is_given(self):
        watch.atomic_json(self.path, dict(BASE, mail_enabled_since='2026-11-01T00:00:00+00:00'))
        smtp_mail.configure_mail(self.path, SENDER, TO, now=NOW)
        self.assertEqual(self.config()['mail_enabled_since'], '2026-11-01T00:00:00+00:00')
        smtp_mail.configure_mail(self.path, SENDER, TO, since='2026-11-13T09:00:00+09:00', now=NOW)
        self.assertEqual(self.config()['mail_enabled_since'], '2026-11-13T00:00:00+00:00')

    def test_enable_and_disable_are_explicit(self):
        smtp_mail.configure_mail(self.path, SENDER, TO, enable=True, now=NOW)
        self.assertIs(self.config()['mail_enabled'], True)
        smtp_mail.configure_mail(self.path, SENDER, TO, enable=False, now=NOW)
        self.assertIs(self.config()['mail_enabled'], False)
        smtp_mail.configure_mail(self.path, SENDER, TO, now=NOW)
        self.assertIs(self.config()['mail_enabled'], False)  # left as it was

    def test_invalid_input_leaves_the_file_untouched(self):
        before = self.path.read_bytes()
        for sender, to, since in (('someone@example.com', TO, None),        # not a Gmail sender
                                  ('not-an-address', TO, None),
                                  (SENDER, 'nobody', None),
                                  (SENDER, TO, '2026-11-13 09:00'),           # no time zone
                                  (SENDER, TO, 'tomorrow')):
            with self.assertRaises(ValueError, msg=(sender, to, since)):
                smtp_mail.configure_mail(self.path, sender, to, since=since, now=NOW)
        self.assertEqual(self.path.read_bytes(), before)

    def test_nothing_secret_is_written(self):
        smtp_mail.configure_mail(self.path, SENDER, TO, enable=True, now=NOW)
        added = set(self.config()) - set(BASE)
        self.assertEqual(added, {'mail_provider', 'mail_sender', 'mail_to', 'mail_enabled_since', 'mail_enabled'})
        self.assertNotIn('password', json.dumps(self.config()).lower())

    def test_missing_config_is_an_error_not_a_new_file(self):
        missing = self.path.with_name('absent.json')
        with self.assertRaises(FileNotFoundError):
            smtp_mail.configure_mail(missing, SENDER, TO, now=NOW)
        self.assertFalse(missing.exists())

    def test_command_line(self):
        argv = ['smtp_mail.py', 'configure', '--config', str(self.path), '--sender', SENDER, '--to', TO, '--enable']
        with mock.patch.object(sys, 'argv', argv), mock.patch('builtins.print'):
            self.assertEqual(smtp_mail.main(), 0)
        config = self.config()
        self.assertEqual((config['mail_sender'], config['mail_to'], config['mail_enabled']), (SENDER, TO, True))


if __name__ == '__main__':
    unittest.main()
