"""Only temporary documents and archived synthetic observations are mutated."""
from copy import deepcopy
from hashlib import sha256
from html import unescape
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('choice_display_test', SCRIPTS / 'choice_sync_status.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class FakeController:
    def __init__(self, root):
        self.workspace = root / 'workspace'
        self.logs = self.workspace / 'driver_logs'
        self.logs.mkdir(parents=True)
        self.state = {'partial_records': [], 'record_identity_mismatch': [], 'pending_record_journals': [],
                      'running': [], 'unrecorded': [], 'unresolved_failures': [], 'unresolved_launches': [],
                      'recorded_cells': 0, 'registered_cells': 70, 'next_cell': {'cell_id': 'registered_next'},
                      'core_ready': False, 'core_start_available': False}

    def status(self, inspect_processes=False):
        return deepcopy(self.state)

    def records(self):
        return []


class CurrentDisplayContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.out = self.root / '06_研究結果/jdrt/goal_20261017'
        self.out.mkdir(parents=True)
        self.controller = FakeController(self.root)
        self.summary = '最新HOLD：goal ACTIVE。正式記録0/70、研究core稼働0、技術READY=false。旧failed保全。'
        self.tail = '履歴：変更しない & <code>old</code>。<!-- choice_record:old-accepted -->'.encode()
        self.context = self.root / sync.DISPLAY_FILES[0]
        self.context.write_bytes(b'\xef\xbb\xbf' + '# context\r\r\n**最終更新：** 2001-02-03\r\r\n\r\r\n**'.encode()
                                 + self.summary.encode() + b'**\r\r\n' + self.tail + b'\r\r\n')
        self.markdown = self.root / sync.DISPLAY_FILES[1]
        self.markdown.parent.mkdir(parents=True)
        self.markdown.write_bytes(b'\xef\xbb\xbf' + '# md\r\n >**手動更新された最新HOLD：'.encode()
                                  + self.summary.encode() + b'**\r\n' + '> **最終更新：** 2001-02-03  \r\n'.encode() + self.tail + b'\r\n')
        # Migration deliberately uses the existing latest-HOLD prefix while its text differs from checkpoint.
        self.markdown.write_bytes(self.markdown.read_bytes().replace('手動更新された最新HOLD：'.encode(), '最新HOLD：手動差分。'.encode()))
        self.html = self.root / sync.DISPLAY_FILES[2]
        self.html.write_bytes(b'\xef\xbb\xbf<body><aside data-choice-technical-hold="old"><strong>different &amp; old</strong></aside>\n'
                              b'<p class="snapshot">2001-02-03' + '更新</p>\n'.encode()
                              + b'<aside class="callout" id="choice-current-hold"><h2>old</h2><p>different <code>HTML</code></p></aside>\n'
                              + self.tail + b'\n<footer class="site-footer">\n<p>2001-02-03' + '更新</p>\n</footer>'.encode())
        self.task = self.root / '05_タスク管理/jdrt/JDRT-受付代替行動_詳細タスク.md'
        self.task.parent.mkdir(parents=True)
        self.task.write_bytes(b'\xef\xbb\xbfTASK\r\n| CH-M1 | monitor | lifecycle | old latest |\r\n' + self.tail + b'\r\n')
        self.source = self.root / 'owned.py'
        self.source.write_bytes(b'current implementation\n')
        self.cfg = self.root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text(json.dumps({'execution': {'implementation_files': ['owned.py']}}), encoding='utf-8')
        self.checkpoint = self.out / 'G4実装・実SUMO_継続チェックポイント.json'
        self.cp = {'at_jst': '2001-02-03T04:05:06+09:00', 'summary': self.summary, 'goal_status': 'ACTIVE',
                   'technical_ready': False, 'preflight_state': 'READY current old-version',
                   'smoke_sequence_status': 'COMPLETED 14 PASS', 'independent_audit_status': 'PASS',
                   'current_implementation_sha256': {'owned.py': 'old SHA'}, 'other_history': {'preserve': ['old', 'PASS']}}
        self.checkpoint.write_bytes(b'\xef\xbb\xbf' + (json.dumps(self.cp, ensure_ascii=False, indent=2) + '\n').encode().replace(b'\n', b'\r\n'))
        self.report = self.out / 'canonical.json'
        self.snapshot = self.out / 'canonical.state.snapshot.bin'
        owner = {'ProcessId': 123, 'ParentProcessId': 1, 'CreationDate': '/Date(1000)/',
                 'ExecutablePath': 'python.exe', 'CommandLine': 'python build.py'}
        child = {'ProcessId': 456, 'ParentProcessId': 123, 'CreationDate': '/Date(2000)/',
                 'ExecutablePath': 'cmake.exe', 'CommandLine': 'cmake --build isolated'}
        state = {'schema': 'isolated_native_build_v1', 'attempt_id': 'artificial-attempt', 'status': 'RUNNING',
                 'phase': 'compile<script>&"', 'owner_pid': 123, 'child_pid': 456,
                 'owner_process_identity': owner, 'simulation_allowed': False, 'research_cli_switch_allowed': False,
                 'commands': [{'pid': 456, 'phase': 'compile<script>&"', 'process_identity': child}]}
        raw = b'\xef\xbb\xbf' + json.dumps(state).encode()
        self.snapshot.write_bytes(raw)
        self.observation = {'action': 'isolated_native_build_monitor', 'at_jst': '2001-02-04T05:06:07+09:00',
                            'report': self.report.relative_to(self.root).as_posix(),
                            'state_snapshot_file': self.snapshot.relative_to(self.root).as_posix(),
                            'state_snapshot_sha256': sha256(raw).hexdigest(), 'state_snapshot_bytes': len(raw),
                            'state_snapshot': state, 'anomaly_flags': [],
                            **{key: False for key in ('formal_validation_or_adoption', 'core_ready', 'native_regression_verified',
                                                    'downstream_start_permitted', 'simulation_allowed', 'research_cli_switch_allowed')},
                            **{key: state[key] for key in ('status', 'phase', 'attempt_id')}}
        for role, expected in (('owner', owner), ('child', child)):
            actual = {**expected, 'CreationDate': 1000 if role == 'owner' else 2000}
            self.observation[role] = {'pid': expected['ProcessId'], 'identity': 'matched', 'expected': expected, 'observed_cim': actual}
        self.save_observation()

    def save_observation(self):
        self.report.write_text(json.dumps(self.observation, ensure_ascii=False), encoding='utf-8')

    def run_sync(self, **kwargs):
        return sync.synchronize(self.root, controller=self.controller, **kwargs)

    def originals(self):
        return {p: p.read_bytes() for p in (self.context, self.markdown, self.html, self.task, self.checkpoint)}

    def test_manual_migration_preview_is_read_only_and_html_is_separately_escaped(self):
        originals = self.originals()
        result = self.run_sync(build_report=self.report)
        self.assertEqual(originals, self.originals())
        self.assertFalse(result['formal_adoption_created'])
        self.assertIn('2001-02-04T05:06:07+09:00', result['summary'])
        self.assertIn('ポイント観測', result['summary'])
        self.assertIn('開始許可ではない', result['summary'])
        self.run_sync(build_report=self.report, apply=True)
        html = self.html.read_bytes().decode('utf-8-sig')
        top = re.search(r'<!-- CHOICE_CURRENT_HTML_TOP_BEGIN -->.*?<p>(.*?)</p>', html, re.S).group(1)
        self.assertEqual(unescape(top), result['summary'])
        self.assertNotIn('<script>', top)
        self.assertIn('&lt;script&gt;', top)
        self.assertNotIn('**', top)
        self.assertIn('2001-02-04：', html)
        self.assertIn('2001-02-04更新', html)

    def test_apply_preserves_bom_eol_unmanaged_bytes_and_acceptance_markers(self):
        originals = self.originals()
        self.run_sync(build_report=self.report, apply=True)
        for path in (self.context, self.markdown, self.html, self.task):
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            self.assertIn(self.tail, raw)
            self.assertNotIn(b'\0', raw)
            self.assertEqual(re.findall(rb'<!-- choice_record.*?-->', raw), re.findall(rb'<!-- choice_record.*?-->', originals[path]))
        self.assertTrue(self.context.read_bytes().endswith(b'\r\r\n' + self.tail + b'\r\r\n'))
        self.assertTrue(self.markdown.read_bytes().endswith(b'> **' + '最終更新：** 2001-02-04  \r\n'.encode() + self.tail + b'\r\n'))
        self.assertTrue(self.task.read_bytes().endswith(b'\r\n' + self.tail + b'\r\n'))
        history = self.out / 'document_history'
        for path, raw in originals.items():
            self.assertEqual((history / (sha256(raw).hexdigest() + path.suffix)).read_bytes(), raw)

    def test_same_report_reapply_is_byte_idempotent_including_operation_logs(self):
        self.run_sync(build_report=self.report, apply=True)
        original = self.originals()
        operations = (self.out / 'operations.jsonl').read_bytes()
        result = self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(result['changed_files'], [])
        self.assertEqual(self.originals(), original)
        self.assertEqual((self.out / 'operations.jsonl').read_bytes(), operations)

    def test_old_ready_is_historical_and_current_hash_is_derived_from_config(self):
        self.run_sync(build_report=self.report, apply=True)
        current = sync.read_json(self.checkpoint)
        self.assertFalse(current['technical_ready'])
        self.assertTrue(current['preflight_state'].startswith('STALE historical:'))
        self.assertTrue(current['independent_audit_status'].startswith('STALE historical:'))
        self.assertEqual(current['current_implementation_sha256'], {'owned.py': sync.file_sha(self.source)})
        self.assertEqual(current['other_history'], self.cp['other_history'])
        old = sync.read_json(self.root / current['historical_display_checkpoints'][0]['file'])
        self.assertEqual(old['preflight_state'], self.cp['preflight_state'])

    def test_normal_mode_keeps_existing_technical_hold(self):
        result = self.run_sync(apply=True)
        self.assertEqual(result['summary'], self.summary)
        self.assertNotIn('次の登録セル', result['summary'])
        self.assertEqual(self.run_sync(apply=True)['changed_files'], [])

    def test_partial_record_stops_before_any_display_or_checkpoint_write(self):
        originals = self.originals()
        self.controller.state['partial_records'] = ['partial']
        with self.assertRaisesRegex(RuntimeError, 'Partial'):
            self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(self.originals(), originals)

    def test_bad_snapshot_adoption_or_pid_identity_is_rejected(self):
        for key, value in (('state_snapshot_sha256', 'wrong'), ('core_ready', True), ('formal_validation_or_adoption', True)):
            prior = deepcopy(self.observation)
            with self.subTest(key=key):
                self.observation[key] = value
                self.save_observation()
                with self.assertRaises(ValueError):
                    self.run_sync(build_report=self.report, apply=True)
            self.observation = prior
        self.observation['owner']['observed_cim']['CommandLine'] = 'different process'
        self.save_observation()
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.run_sync(build_report=self.report)

    def test_atomic_write_failure_restores_every_original_byte(self):
        originals = self.originals()
        atomic = sync.atomic_bytes
        count = 0
        def fail_once(path, raw):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('synthetic write failure')
            atomic(path, raw)
        with patch.object(sync, 'atomic_bytes', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'synthetic'):
                self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(self.originals(), originals)

    def test_status_change_after_preview_is_rejected(self):
        original = self.originals()
        state = self.controller.status()
        changed = {**state, 'unrecorded': ['arrived-during-preview']}
        with patch.object(self.controller, 'status', side_effect=[state, changed]):
            with self.assertRaisesRegex(RuntimeError, 'status changed'):
                self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(self.originals(), original)

    def test_terminal_failure_with_absent_owner_and_no_child_is_point_evidence(self):
        state = self.observation['state_snapshot']
        state.update(status='FAILED_PRESERVED', phase='failed_link', child_pid=None)
        self.observation.update(status=state['status'], phase=state['phase'], child=None,
                                anomaly_flags=['terminal_build_FAILED_PRESERVED'])
        self.observation['owner'].update(identity='absent', observed_cim=None)
        raw = json.dumps(state).encode()
        self.snapshot.write_bytes(raw)
        self.observation.update(state_snapshot_sha256=sha256(raw).hexdigest(), state_snapshot_bytes=len(raw))
        self.save_observation()
        result = self.run_sync(build_report=self.report, apply=True)
        self.assertIn('FAILED_PRESERVED', result['summary'])
        self.assertIn('identity=absent', result['summary'])
        self.assertIn('native回帰', result['summary'])
        self.assertIn('技術READY=false', result['summary'])

    def test_ordinary_active_core_is_identified_without_adopting_it(self):
        self.cp.update(technical_ready=True, summary='最終goal ACTIVE。通常core表示。',
                       current_implementation_sha256={'owned.py': sync.file_sha(self.source)})
        self.checkpoint.write_text(json.dumps(self.cp, ensure_ascii=False), encoding='utf-8')
        manifest = self.root / 'workspace/runs/owned/manifest.json'
        manifest.parent.mkdir(parents=True)
        self.controller.state['running'] = ['owned']
        run = {'purpose': 'core', 'run_id': 'owned', 'cell_id': 'cell', 'pid': 123, 'status': 'RUNNING', 'end_sec': 10}
        with patch.object(self.controller, 'records', return_value=[(manifest, run)]), patch.object(sync, 'pid_alive', return_value=True):
            result = self.run_sync(apply=True)
        self.assertIn('owned（cell）RUNNING', result['summary'])
        self.assertIn('開始許可ではない', result['summary'])
        self.assertEqual(result['recorded_cells'], 0)
        self.assertFalse(result['formal_adoption_created'])

    def test_atomic_replace_failure_cleans_own_temp_and_rolls_back(self):
        original = self.originals()
        replace = sync.os.replace
        count = 0
        def fail_once(source, target):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('synthetic replace failure')
            replace(source, target)
        with patch.object(sync.os, 'replace', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'replace failure'):
                self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(self.originals(), original)
        self.assertFalse(list(self.root.rglob('*.choice_sync.tmp')))

    def test_nul_or_ambiguous_current_markers_stop_without_writing(self):
        for suffix in (b'\0', b'<!-- CHOICE_CURRENT_CONTEXT_BEGIN -->'):
            original = self.context.read_bytes()
            self.context.write_bytes(original + suffix)
            before = self.originals()
            with self.assertRaises(ValueError):
                self.run_sync(build_report=self.report, apply=True)
            self.assertEqual(self.originals(), before)
            self.context.write_bytes(original)

    def test_corrupt_history_or_existing_writer_lock_prevents_changes(self):
        original = self.originals()
        history = self.out / 'document_history'
        history.mkdir()
        archive = history / (sha256(original[self.context]).hexdigest() + '.md')
        archive.write_bytes(b'corrupt old backup')
        with self.assertRaisesRegex(RuntimeError, 'archive bytes'):
            self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(self.originals(), original)
        archive.unlink()
        lock = self.controller.logs / 'writer.lock'
        lock.write_bytes(b'other writer')
        with self.assertRaises(FileExistsError):
            self.run_sync(build_report=self.report, apply=True)
        self.assertEqual(lock.read_bytes(), b'other writer')
        self.assertEqual(self.originals(), original)


if __name__ == '__main__':
    unittest.main()
