"""Monitoring must not signal or terminate the owned test process."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import unittest
import tempfile
import json
import os
import time
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[2] / '.agents/skills/joso-jdrt-runner/scripts/realtime_choice_cell.py'
spec = importlib.util.spec_from_file_location('choice_skill_liveness_test', FILE)
skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill)


class ReadOnlyLiveness(unittest.TestCase):
    def test_real_venv_launcher_and_executor_identity_are_both_live_and_related(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'owned_child.json'
            code = ('import json,os,sys,time;'
                    'open(sys.argv[1],"w").write(json.dumps({"pid":os.getpid(),"parent":os.getppid()}));'
                    'time.sleep(30)')
            child = subprocess.Popen([sys.executable, '-c', code, str(receipt)], stdin=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if receipt.exists() and receipt.stat().st_size:
                        break
                    time.sleep(.05)
                actual = json.loads(receipt.read_text())
                self.assertTrue(skill.pid_alive(child.pid))
                self.assertTrue(skill.pid_alive(actual['pid']))
                self.assertTrue(skill.reserved_executor_identity(child.pid, actual['pid'], actual['parent'], os.name == 'nt'))
                self.assertFalse(skill.reserved_executor_identity(child.pid, actual['pid'] + 100000, actual['parent'] + 100000, os.name == 'nt'))
            finally:
                # Windows TerminateProcess on the redirector alone does not
                # terminate its owned child. Terminate that test child explicitly.
                if receipt.exists() and os.name == 'nt':
                    actual = json.loads(receipt.read_text())
                    if actual['pid'] != child.pid:
                        subprocess.run(['taskkill', '/PID', str(actual['pid']), '/F'], capture_output=True, check=False)
                if child.poll() is None:
                    child.terminate()
                child.wait()

    def test_live_owned_child_survives_probe_and_exit_is_recognized(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            self.assertTrue(skill.pid_alive(child.pid))
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait()
        self.assertFalse(skill.pid_alive(child.pid))

    def test_invalid_ids_fail_closed(self):
        for value in (0, -1, '42'):
            with self.assertRaises(ValueError):
                skill.pid_alive(value)


class ProgressDateContracts(unittest.TestCase):
    def test_dates_are_sorted_collapsible_and_text_is_escaped(self):
        md = ('<!-- PROGRESS_LOG_BEGIN -->\n### 2026-01-01\n- Earlier\n'
              '### 2026-01-03\n- Recent <script> & safe\n<!-- PROGRESS_LOG_END -->')
        result = skill.render_progress(md)
        self.assertLess(result.index('2026-01-03'), result.index('2026-01-01'))
        self.assertEqual(result.count('<details open>'), 1)
        self.assertEqual(result.count('<details'), 2)
        self.assertIn('&lt;script&gt; &amp; safe', result)

    def test_formal_record_updates_markdown_before_derived_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = SixFileRecordContracts().fixture(directory)
            params['record_files'][4:5] = ['status.md', 'status.html']
            md = '# Status\n<!-- PROGRESS_LOG_BEGIN -->\n### 2026-01-01\n- Before\n<!-- PROGRESS_LOG_END -->\n'
            html = '<html><main><!-- PROGRESS_HTML_BEGIN -->old<!-- PROGRESS_HTML_END --></main></html>'
            (root / 'status.md').write_text(md, encoding='utf-8')
            (root / 'status.html').write_text(html, encoding='utf-8')
            entry['recorded_at_jst'] = '2026-01-03T10:00:00+09:00'
            skill.record_six_files(root, params, entry, 'Full evidence')
            updated = (root / 'status.md').read_text(encoding='utf-8')
            result = (root / 'status.html').read_text(encoding='utf-8')
            self.assertIn('### 2026-01-03', updated)
            self.assertIn(entry['run_id'], updated)
            self.assertIn(skill.render_progress(updated), result)
            self.assertEqual(len((root / 'ledger.jsonl').read_text().splitlines()), 1)
            self.assertEqual(skill.record_six_files(root, params, entry, 'Full evidence')['status'], 'ALREADY_RECORDED')

    def test_html_failure_rolls_back_markdown_and_all_seven_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = SixFileRecordContracts().fixture(directory)
            params['record_files'][4:5] = ['status.md', 'status.html']
            (root / 'status.md').write_text('<!-- PROGRESS_LOG_BEGIN -->\n<!-- PROGRESS_LOG_END -->', encoding='utf-8')
            (root / 'status.html').write_text('<!-- PROGRESS_HTML_BEGIN --><!-- PROGRESS_HTML_END -->', encoding='utf-8')
            entry['recorded_at_jst'] = '2026-01-03T10:00:00+09:00'
            before = {n: (root / n).read_bytes() for n in params['record_files'][:-1]}
            original_write = Path.write_text
            def fail_html(path, *args, **kwargs):
                if path == root / 'status.html':
                    raise OSError('Injected HTML write failure')
                return original_write(path, *args, **kwargs)
            with patch.object(Path, 'write_text', fail_html):
                with self.assertRaisesRegex(OSError, 'Injected HTML'):
                    skill.record_six_files(root, params, entry, 'Full evidence')
            self.assertEqual(before, {n: (root / n).read_bytes() for n in before})
            self.assertFalse((root / 'ledger.jsonl').exists())

    def test_duplicate_dates_are_rejected(self):
        md = '<!-- PROGRESS_LOG_BEGIN -->\n### 2026-01-01\n- A\n### 2026-01-01\n- B\n<!-- PROGRESS_LOG_END -->'
        with self.assertRaises(ValueError):
            skill.render_progress(md)


class SixFileRecordContracts(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        names = ['records.md', 'tasks.md', 'context.md', 'decisions.md', 'progress.md', 'ledger.jsonl']
        params = {'protocol': 'isolated_test', 'workspace': 'owned_workspace', 'record_files': names}
        for name in names[:-1]:
            contents = '# Original\r\n' + ('\r\n<!-- AGENT_CURRENT_END -->\r\n# History\r\n' if name == 'context.md' else '')
            (root / name).write_bytes(contents.encode('utf-8'))
        entry = {'run_id': 'owned_test', 'cell_id': 'cell', 'protocol': params['protocol'], 'purpose': 'core',
                 'validation_status': 'PASS', 'implementation_sha256': {'owned': 'sha'},
                 'input_manifest_sha256': 'input', 'manifest_sha256': 'manifest'}
        return root, params, entry

    def test_html_record_is_escaped_inside_document_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            params['record_files'][4] = 'progress.html'
            original = '<html><body><main><!-- PROGRESS_ENTRIES --></main></body></html>'
            path = root / 'progress.html'
            path.write_text(original, encoding='utf-8')
            skill.record_six_files(root, params, entry, 'Observed <script> & result')
            result = path.read_text(encoding='utf-8')
            self.assertIn('&lt;script&gt; &amp; result', result)
            self.assertLess(result.index(entry['run_id']), result.index('</main>'))
            self.assertEqual(result.count('<!-- PROGRESS_ENTRIES -->'), 1)
            self.assertEqual(skill.record_six_files(root, params, entry, 'Same')['status'], 'ALREADY_RECORDED')
            self.assertEqual(path.read_text(encoding='utf-8'), result)
            self.assertEqual((root / 'progress.md').read_bytes(), b'# Original\r\n')

    def test_missing_html_marker_preserves_all_record_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            params['record_files'][4] = 'progress.html'
            (root / 'progress.html').write_text('<html><body></body></html>', encoding='utf-8')
            before = {n: (root / n).read_bytes() for n in params['record_files'][:-1]}
            with self.assertRaisesRegex(RuntimeError, 'HTML progress insertion marker'):
                skill.record_six_files(root, params, entry, 'Owned')
            self.assertEqual(before, {n: (root / n).read_bytes() for n in before})
            self.assertFalse((root / 'ledger.jsonl').exists())

    def test_commit_idempotence_and_six_file_presence(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            result = skill.record_six_files(root, params, entry, 'Owned test data only')
            self.assertEqual(result['status'], 'RECORDED')
            for name in params['record_files']:
                self.assertIn(entry['run_id'], (root / name).read_text(encoding='utf-8'))
            context = (root / 'context.md').read_text(encoding='utf-8')
            self.assertLess(context.index('choice_record:'), context.index('<!-- AGENT_CURRENT_END -->'))
            self.assertTrue(context.endswith('# History\n'))
            before = {name: (root / name).read_bytes() for name in params['record_files']}
            self.assertEqual(skill.record_six_files(root, params, entry, 'Owned test data only')['status'], 'ALREADY_RECORDED')
            self.assertEqual(before, {name: (root / name).read_bytes() for name in params['record_files']})

    def test_write_failure_restores_original_bytes_and_absent_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            before = {name: (root / name).read_bytes() for name in params['record_files'][:-1]}
            original = Path.write_text
            def interrupted(path, *args, **kwargs):
                if path == root / 'decisions.md':
                    raise OSError('Owned injected write failure')
                return original(path, *args, **kwargs)
            with patch.object(Path, 'write_text', interrupted), self.assertRaises(OSError):
                skill.record_six_files(root, params, entry, 'Owned test data only')
            self.assertEqual(before, {name: (root / name).read_bytes() for name in before})
            self.assertFalse((root / 'ledger.jsonl').exists())
            journal = next((root / params['workspace'] / 'record_transactions').glob('*/journal.json'))
            self.assertEqual(json.loads(journal.read_text())['status'], 'ROLLED_BACK')
            self.assertTrue(json.loads(journal.read_text())['rollback_verified'])

    def test_writer_lock_and_prepared_crash_journal_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            workspace = root / params['workspace']
            with skill.single_writer(workspace):
                with self.assertRaises(FileExistsError):
                    skill.record_six_files(root, params, entry, 'Owned')
            pending = workspace / 'record_transactions/owned_pending'
            pending.mkdir(parents=True)
            (pending / 'journal.json').write_text(json.dumps({'status': 'PREPARED'}))
            with self.assertRaisesRegex(RuntimeError, 'Unresolved'):
                skill.record_six_files(root, params, entry, 'Owned')

    def test_partial_document_repair_does_not_duplicate_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            skill.record_six_files(root, params, entry, 'Owned')
            (root / 'tasks.md').write_text('# Restored original\n', encoding='utf-8')
            self.assertEqual(skill.record_six_files(root, params, entry, 'Owned')['status'], 'RECORDED')
            self.assertEqual(len((root / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()), 1)

    def test_duplicate_cell_foreign_protocol_and_non_core_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, params, entry = self.fixture(directory)
            for change in ({'purpose': 'fixture'}, {'validation_status': 'INVALID'}, {'protocol': 'foreign'}):
                with self.assertRaises(ValueError):
                    skill.record_six_files(root, params, {**entry, **change}, 'Owned')
            skill.record_six_files(root, params, entry, 'Owned')
            with self.assertRaisesRegex(RuntimeError, 'another accepted'):
                skill.record_six_files(root, params, {**entry, 'run_id': 'owned_other'}, 'Owned')


class AtomicCheckpointContracts(unittest.TestCase):
    def test_transient_replace_denial_retries_but_persistent_denial_never_succeeds(self):
        from scripts import jdrt_realtime_choice as runtime
        for writer in (skill.save_json, runtime.atomic_json):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'owned.json'
                original = Path.replace
                attempts = []
                def denied_once(source, target):
                    attempts.append(1)
                    if len(attempts) == 1:
                        raise PermissionError('Owned transient denial')
                    return original(source, target)
                with patch.object(Path, 'replace', denied_once), patch.object(time, 'sleep'):
                    writer(path, {'owned': True})
                self.assertEqual(json.loads(path.read_text()), {'owned': True})
                self.assertEqual(len(attempts), 2)
                with patch.object(Path, 'replace', side_effect=PermissionError('Owned persistent denial')) as replace, patch.object(time, 'sleep'):
                    with self.assertRaises(PermissionError):
                        writer(path, {'owned': False})
                self.assertEqual(replace.call_count, 6)
                self.assertEqual(json.loads(path.read_text()), {'owned': True})


class LifecycleContracts(unittest.TestCase):
    def setup_controller(self, directory):
        root, params, entry = SixFileRecordContracts().fixture(directory)
        params.update(cells=[{'cell_id': 'cell', 'scenario': 'R0', 'seed': 1,
                             'destination_policy': 'fixed_reference', 'demand_level': None}],
                      execution={'implementation_files': ['owned.py']})
        path = root / '04_プログラム/config/jdrt_realtime_choice_v1.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(params), encoding='utf-8')
        (root / 'owned.py').write_text('# Owned isolated source\n', encoding='utf-8')
        controller = skill.ChoiceController(root)
        folder = controller.workspace / 'runs/owned_test'
        folder.mkdir(parents=True)
        manifest = {'protocol': params['protocol'], 'run_id': 'owned_test', 'purpose': 'core', 'status': 'COMPLETED',
                    'pid': 999999, **params['cells'][0], 'input_manifest_sha256': 'owned-input',
                    'implementation_sha256': controller.implementation()}
        skill.save_json(folder / 'manifest.json', manifest)
        proof = controller.workspace / 'validation_reports/owned.json'
        proof.parent.mkdir()
        metrics = {k: 0 for k in ('people', 'requests', 'primary_admitted', 'primary_denominator', 'primary_boundary_exit_separate')}
        validation = {'status': 'PASS', 'core_adoption_permitted': True,
                      'manifest_sha256': skill.file_sha(folder / 'manifest.json'),
                      'validation_report': proof.relative_to(root).as_posix(),
                      'components': {'person_tables': metrics}}
        skill.save_json(proof, validation)
        return controller, manifest, validation

    def test_status_blocks_completed_unrecorded_and_record_requires_adoption(self):
        with tempfile.TemporaryDirectory() as directory:
            c, m, v = self.setup_controller(directory)
            with patch.object(c, 'process_inventory', return_value=[]):
                self.assertEqual(c.status()['unrecorded'], [m['run_id']])
                with self.assertRaises(RuntimeError):
                    c.assert_idle()
                with patch.object(c, 'validate', return_value={**v, 'core_adoption_permitted': False}):
                    with self.assertRaisesRegex(RuntimeError, 'Formal independent'):
                        c.record(m['run_id'])
                self.assertFalse((c.root / c.parameters['record_files'][-1]).exists())

    def test_record_wrapper_and_next_cell_follow_six_files(self):
        with tempfile.TemporaryDirectory() as directory:
            c, m, v = self.setup_controller(directory)
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(c, 'validate', return_value=v):
                self.assertEqual(c.record(m['run_id'])['status'], 'RECORDED')
                self.assertEqual(c.status()['recorded_cells'], len(c.parameters['cells']))
                self.assertIsNone(c.status()['next_cell'])
                self.assertEqual(c.record(m['run_id'])['status'], 'ALREADY_RECORDED')
                self.assertEqual(len(c.ledger()), 1)

    def test_orphan_recovery_preserves_original_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            c, m, v = self.setup_controller(directory)
            path, m = c.find(m['run_id'])
            m['status'] = 'RUNNING'
            skill.save_json(path, m)
            original = path.read_bytes()
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(skill, 'pid_alive', return_value=False):
                result = c.recover_run(m['run_id'], 'Owned orphan test')
            self.assertEqual(result['status'], 'FAILED_PRESERVED')
            diagnosis = json.loads((c.logs / (m['run_id'] + '.diagnosis.json')).read_text())
            self.assertEqual((c.root / diagnosis['original_manifest']).read_bytes(), original)
            self.assertEqual(json.loads(path.read_text())['status'], 'FAILED')

    def prepared_record(self, c, m, v):
        with patch.object(c, 'process_inventory', return_value=[]), patch.object(c, 'validate', return_value=v):
            c.record(m['run_id'])
        path = next((c.workspace / 'record_transactions').glob('*/journal.json'))
        journal = json.loads(path.read_text())
        journal['status'] = 'PREPARED'
        skill.save_json(path, journal)
        return path, journal

    def test_crashed_partial_ledger_recovers_exact_six_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            c, m, v = self.setup_controller(directory)
            original = {name: (c.root / name).read_bytes() if (c.root / name).exists() else None for name in c.parameters['record_files']}
            path, journal = self.prepared_record(c, m, v)
            ledger = c.root / c.parameters['record_files'][-1]
            ledger.write_bytes(ledger.read_bytes()[:20])
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(skill, 'pid_alive', return_value=False):
                self.assertEqual(c.recover_record(path.parent.name, 'Owned crash test')['status'], 'RECOVERED_ROLLBACK')
            for name, before in original.items():
                if before is None:
                    self.assertFalse((c.root / name).exists())
                else:
                    self.assertEqual((c.root / name).read_bytes(), before)

    def test_prepared_not_adopted_and_unrelated_edit_blocks_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            c, m, v = self.setup_controller(directory)
            path, journal = self.prepared_record(c, m, v)
            self.assertEqual(c.status()['recorded_cells'], 0)
            target = c.root / c.parameters['record_files'][0]
            target.write_text('Unrelated owned-test edit', encoding='utf-8')
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(skill, 'pid_alive', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'unrelated change'):
                    c.recover_record(path.parent.name, 'Owned conflict test')
            self.assertEqual(target.read_text(), 'Unrelated owned-test edit')


class LaunchContracts(unittest.TestCase):
    def controller(self, directory):
        c, m, v = LifecycleContracts().setup_controller(directory)
        path, _ = c.find(m['run_id'])
        path.unlink()  # This isolated fixture is not a research run.
        return c

    def test_no_READY_or_active_native_process_never_spawns_child(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.controller(directory)
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(c, 'ready', return_value=False), patch.object(
                    skill.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(RuntimeError, 'READY'):
                    c.launch('owned_new')
                spawn.assert_not_called()
            with patch.object(c, 'process_inventory', return_value=[{'ProcessId': 1, 'Name': 'owned'}]), patch.object(
                    skill.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(RuntimeError, 'blocks mutation'):
                    c.launch('owned_new')
                spawn.assert_not_called()

    def test_launch_reserves_one_cell_and_never_reuses_ID(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.controller(directory)
            skill.save_json(c.root / 'reserve.json', {'one_run_reserve_bytes': 1})
            skill.save_json(c.workspace / 'preflight_ready.json', {'evidence': {'storage': 'reserve.json'}})
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(c, 'ready', return_value=True), patch.object(
                    skill.subprocess, 'Popen') as spawn:
                spawn.return_value.pid = 765432
                result = c.launch('owned_new')
                self.assertEqual(result['cell_id'], c.parameters['cells'][0]['cell_id'])
                self.assertEqual(spawn.call_count, 1)
                state = json.loads((c.logs / 'owned_new.state.json').read_text(encoding='utf-8'))
                self.assertEqual(state['pid'], 765432)
                self.assertEqual(state['status'], 'LAUNCHED')
                with self.assertRaisesRegex(RuntimeError, 'blocks mutation'):
                    c.launch('owned_other')
                self.assertEqual(spawn.call_count, 1)

    def test_failed_spawn_is_preserved_and_explicit_recovery_required(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.controller(directory)
            skill.save_json(c.root / 'reserve.json', {'one_run_reserve_bytes': 1})
            skill.save_json(c.workspace / 'preflight_ready.json', {'evidence': {'storage': 'reserve.json'}})
            with patch.object(c, 'process_inventory', return_value=[]), patch.object(c, 'ready', return_value=True), patch.object(
                    skill.subprocess, 'Popen', side_effect=OSError('Owned injected Popen failure')):
                with self.assertRaises(OSError):
                    c.launch('owned_failed')
                self.assertIn('owned_failed', c.status()['unresolved_launches'])
                original = (c.logs / 'owned_failed.state.json').read_bytes()
                with patch.object(skill, 'pid_alive', return_value=False):
                    result = c.recover_launch('owned_failed', 'Owned failed launch diagnosis')
                self.assertEqual(result['status'], 'FAILED_LAUNCH_PRESERVED')
                self.assertEqual((c.root / result['original_state']).read_bytes(), original)
                with self.assertRaisesRegex(RuntimeError, 'already been used'):
                    c.launch('owned_failed')

    def test_foreign_RUNNING_manifest_holds_next_start(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.controller(directory)
            skill.save_json(c.workspace.parent / 'owned_foreign/runs/old/manifest.json', {'status': 'RUNNING'})
            with patch.object(c, 'process_inventory', return_value=[]), self.assertRaisesRegex(RuntimeError, 'foreign_running'):
                c.assert_idle()

    def test_real_project_python_child_completes_reserved_execute_handshake_without_SUMO(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.controller(directory)
            ready = c.workspace / 'preflight_ready.json'
            skill.save_json(ready, {'owned_identity_test_only': True})
            state = {'run_id': 'owned_handshake', 'cell_id': 'cell', 'purpose': 'core', 'status': 'PREPARED',
                     'pid': None, 'implementation_sha256': c.implementation(), 'ready_sha256': skill.file_sha(ready)}
            state_path = c.logs / 'owned_handshake.state.json'
            skill.save_json(state_path, state)
            code = ('import importlib.util,json,sys;from pathlib import Path;from unittest.mock import patch;'
                    'sys.path.insert(0,sys.argv[3]);'
                    's=importlib.util.spec_from_file_location("owned_skill",sys.argv[1]);'
                    'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
                    'c=m.ChoiceController(Path(sys.argv[2]));'
                    '\nwith patch("scripts.jdrt_realtime_choice.run",return_value={"owned_mock_no_SUMO":True}) as run:\n'
                    ' result=c.execute("owned_handshake","cell")\n'
                    ' assert run.call_args.args==("cell","owned_handshake") and run.call_args.kwargs=={"purpose":"core"}\n'
                    ' (c.root/"owned_result.json").write_text(json.dumps(result))\n')
            child = subprocess.Popen([sys.executable, '-c', code, str(FILE), str(c.root), str(FILE.parents[4] / '04_プログラム')],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                state.update(status='LAUNCHED', pid=child.pid)
                skill.save_json(state_path, state)
                stdout, stderr = child.communicate(timeout=20)
                self.assertEqual(child.returncode, 0, stderr)
                self.assertTrue(json.loads((c.root / 'owned_result.json').read_text())['owned_mock_no_SUMO'])
                saved = json.loads(state_path.read_text())
                self.assertEqual(saved['launcher_pid'], child.pid)
                self.assertEqual(saved['pid'], saved['executor_pid'])
                self.assertTrue(skill.reserved_executor_identity(saved['launcher_pid'], saved['executor_pid'],
                    saved['executor_parent_pid'], os.name == 'nt'))
                self.assertFalse((c.workspace / 'runs/owned_handshake').exists())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()


if __name__ == '__main__':
    unittest.main()
