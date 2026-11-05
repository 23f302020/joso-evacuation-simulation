"""Artificial orchestration contracts; no research/native commands."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import choice_core_sequence as sequence


class GateTests(unittest.TestCase):
    def setUp(self):
        self.cell = {'cell_id': 'artificial_next'}
        self.status = dict(recorded_cells=3, registered_cells=5,
                           core_ready=True, core_start_available=True,
                           next_cell=self.cell)
        self.holds = ('running', 'unrecorded', 'partial_records',
                      'record_identity_mismatch', 'unresolved_failures',
                      'unresolved_launches', 'pending_record_journals',
                      'foreign_running_manifests', 'active_native_processes')
        self.status.update({key: [] for key in self.holds})

    def test_exact_current_next_is_allowed(self):
        sequence.require_idle(self.status, 3, self.cell)

    def test_every_unresolved_hold_stops(self):
        for key in self.holds:
            with self.subTest(key=key):
                value = copy.deepcopy(self.status)
                value[key] = ['preserve']
                with self.assertRaises(RuntimeError):
                    sequence.require_idle(value, 3, self.cell)

    def test_missing_hold_does_not_default_to_clear(self):
        del self.status['pending_record_journals']
        with self.assertRaises(RuntimeError):
            sequence.require_idle(self.status, 3, self.cell)

    def test_count_cell_or_ready_mismatch_stops(self):
        for key, value in [('recorded_cells', 4), ('next_cell', {'cell_id': 'skipped'}),
                           ('core_ready', False), ('core_start_available', False)]:
            with self.subTest(key=key):
                status = dict(self.status, **{key: value})
                with self.assertRaises(RuntimeError):
                    sequence.require_idle(status, 3, self.cell)

    def test_observer_requires_live_identity_and_freshness(self):
        good = {'monitor_process': {'state': 'alive'},
                'monitor_identity_matches': True, 'observation_age_sec': 10}
        sequence.require_observer(good)
        for key, value in [('monitor_process', {'state': 'absent'}),
                           ('monitor_identity_matches', False),
                           ('observation_age_sec', 121), ('observation_age_sec', -1),
                           ('observation_age_sec', float('nan')), ('observation_age_sec', True)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(RuntimeError):
                    sequence.require_observer(dict(good, **{key: value}))

    def test_readback_precedes_display_writers(self):
        actions = []
        sequence.finish_order(lambda action, run: actions.append(action), 'artificial')
        self.assertEqual(actions, ['finish', 'readback', 'sync'])

    def test_readback_failure_never_runs_display(self):
        actions = []
        def invoke(action, run):
            actions.append(action)
            if action == 'readback':
                raise RuntimeError('Changed terminal document bytes')
        with self.assertRaises(RuntimeError):
            sequence.finish_order(invoke, 'artificial')
        self.assertEqual(actions, ['finish', 'readback'])

    def test_one_invocation_cannot_start_multiple_cells_without_parent_goal_check(self):
        sequence.require_scope(1, 1, 3)
        with self.assertRaisesRegex(RuntimeError, 'one cell'):
            sequence.require_scope(1, 2, 3)


def artificial_proof(cfg, rows):
    return {'status': 'RECORD7_PRIMARY_READBACK_PASS', 'run_id': rows[-1]['run_id'],
            'registration_id': cfg['registration_id'], 'recorded_cells': len(rows),
            'formal_row': rows[-1], 'six_document_single_markers': True,
            'unique_current_registration_ledger': True, 'source_common5_current': True,
            'all_status_holds_clear_at_finish': True,
            'original_and_record_validation_components_differ': []}


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {'protocol': 'realtime_choice_v1', 'registration_id': 'artificial',
                    'cells': [{'cell_id': f'artificial_{i}'} for i in range(3)]}
        self.rows = [{'protocol': self.cfg['protocol'], 'registration_id': 'artificial',
                      'cell_id': 'artificial_0', 'run_id': 'artificial_old'}]
        self.proof = artificial_proof(self.cfg, self.rows)

    def test_readback_requires_same_unique_registered_prefix(self):
        sequence.require_readback(self.proof, self.cfg, 1, self.rows)
        for key, value in [('status', 'INVALID'), ('run_id', 'different'),
                           ('recorded_cells', 2), ('source_common5_current', False),
                           ('six_document_single_markers', False),
                           ('original_and_record_validation_components_differ', ['movement'])]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                sequence.require_readback(dict(self.proof, **{key: value}), self.cfg, 1, self.rows)
        changed = [dict(self.rows[0], registration_id='foreign')]
        with self.assertRaises(RuntimeError):
            sequence.require_readback(artificial_proof(self.cfg, changed), self.cfg, 1, changed)
        skipped = [dict(self.rows[0], cell_id='artificial_2')]
        with self.assertRaises(RuntimeError):
            sequence.require_readback(artificial_proof(self.cfg, skipped), self.cfg, 1, skipped)

    def make_sequence(self, *, fail=None, wrong_start=False):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.root, owner.cfg = self.root, self.cfg
        owner.count, owner.cells, owner.prefix = 1, 2, 'artificial_new'
        owner.state = {'sequence_id': 'artificial', 'completed': []}
        owner.prior_readback = self.root / 'prior.json'
        owner.prior_readback.write_text(json.dumps(self.proof), encoding='utf-8')
        owner.events = []
        owner.save = lambda: None
        owner.event = lambda action, **values: owner.events.append(action)
        owner.observer = lambda: True
        owner.sync = lambda: owner.events.append('sync_start')
        owner.wait_core = lambda rid: owner.events.append('wait_core')
        owner.ledger = lambda: list(self.rows)
        def cli(command, *args):
            if command == 'status':
                cell = self.cfg['cells'][len(self.rows)] if len(self.rows) < 3 else None
                return dict(recorded_cells=len(self.rows), next_cell=cell,
                            registered_cells=len(self.cfg['cells']),
                            core_ready=True, core_start_available=True,
                            **{key: [] for key in sequence.HOLDS})
            self.assertEqual(command, 'start-next')
            owner.events.append('start')
            return dict(status='STARTED', run_id=args[-1],
                        cell_id='wrong' if wrong_start else self.cfg['cells'][len(self.rows)]['cell_id'])
        owner.cli = cli
        def finish(action, rid):
            owner.events.append(action)
            if action == fail:
                raise RuntimeError('Artificial failure')
            if action == 'readback':
                self.rows.append(dict(protocol=self.cfg['protocol'], registration_id='artificial',
                                      cell_id=self.cfg['cells'][len(self.rows)]['cell_id'], run_id=rid))
                owner.prior_readback.write_text(json.dumps(artificial_proof(self.cfg, self.rows)), encoding='utf-8')
        owner.finish_action = finish
        return owner

    def test_two_cells_never_overlap_and_readback_precedes_next_start(self):
        owner = self.make_sequence()
        result = owner.run()
        self.assertEqual(result['status'], 'COMPLETED_REGISTERED_SCOPE_PENDING_ANALYSIS')
        self.assertFalse(result['goal_complete'])
        operations = [a for a in owner.events if a in ('start', 'finish', 'readback', 'sync')]
        self.assertEqual(operations, ['start', 'finish', 'readback', 'sync'] * 2)

    def test_finish_or_readback_failure_preserves_and_never_starts_next(self):
        for action in ('finish', 'readback'):
            with self.subTest(action=action):
                owner = self.make_sequence(fail=action)
                with self.assertRaises(RuntimeError):
                    owner.run()
                self.assertEqual(owner.events.count('start'), 1)
                self.assertEqual(owner.state['status'], 'FAILED_PRESERVED')
                self.assertNotIn('sync', owner.events)

    def test_unexpected_started_cell_stops_without_finish(self):
        owner = self.make_sequence(wrong_start=True)
        with self.assertRaises(RuntimeError):
            owner.run()
        self.assertNotIn('finish', owner.events)

    def test_invalid_monitor_result_does_not_finish_or_retry_core(self):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.command = Mock(return_value={'anomaly_flags': ['SHA_mismatch'], 'status': 'RUNNING'})
        owner.observer = Mock()
        with self.assertRaises(RuntimeError):
            owner.wait_core('artificial')
        self.assertEqual(owner.command.call_count, 1)
        owner.observer.assert_not_called()

    def test_finish_failure_stops_before_reader(self):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.state = {}
        owner.root = self.root
        owner.save = lambda: None
        owner.command = Mock(return_value={'status': 'FAILED_PRESERVED', 'run_id': 'artificial'})
        with self.assertRaises(RuntimeError):
            sequence.finish_order(owner.finish_action, 'artificial')
        self.assertEqual(owner.command.call_count, 1)

    def test_missing_changed_source_prevents_any_child_launch(self):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.root = self.root
        source = self.root / 'source.py'
        source.write_text('before', encoding='utf-8')
        owner.pins = {'source.py': sequence.digest(source)}
        source.write_text('after', encoding='utf-8')
        with patch.object(sequence.subprocess, 'Popen') as launch, self.assertRaises(RuntimeError):
            owner.command('source.py', [])
        launch.assert_not_called()

    def test_terminal_pid_reuse_or_unknown_does_not_grant_finish(self):
        expected = {'state': 'alive', 'pid': 1234, 'created': 111}
        self.assertTrue(sequence.terminal_process_absent({'state': 'absent'}, expected))
        self.assertFalse(sequence.terminal_process_absent(expected, expected))
        for identity, original in [(dict(expected, created=222), expected),
                                   ({'state': 'unknown'}, expected), (expected, None)]:
            with self.subTest(identity=identity), self.assertRaises(RuntimeError):
                sequence.terminal_process_absent(identity, original)

    def test_owned_child_failure_is_logged_once_without_retry(self):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.root, owner.operation = self.root, self.root
        owner.state, owner.serial = {}, 0
        script = self.root / 'artificial_child.py'
        script.write_text('import sys\nprint("preserved output")\nsys.exit(7)\n', encoding='utf-8')
        owner.pins = {'artificial_child.py': sequence.digest(script)}
        with self.assertRaises(RuntimeError):
            owner.command('artificial_child.py', [])
        self.assertEqual(owner.serial, 1)
        self.assertEqual(owner.state['command']['exit_code'], 7)
        self.assertEqual((self.root / '0001.stdout.log').read_text().strip(), 'preserved output')

    def test_completed_manifest_does_not_bypass_real_process_exit(self):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.root = owner.workspace = self.root
        owner.state = {'active': {'process_identity': {'state': 'alive', 'pid': 1234, 'created': 111}}}
        folder = self.root / 'runs/artificial'
        folder.mkdir(parents=True)
        (folder / 'manifest.json').write_text(json.dumps({'pid': 1234}), encoding='utf-8')
        owner.command = Mock(return_value={'status': 'COMPLETED', 'anomaly_flags': []})
        owner.observer = Mock(return_value=True)
        owner.process_identity = Mock(side_effect=[owner.state['active']['process_identity'], {'state': 'absent'}])
        owner.event = Mock()
        with patch.object(sequence.time, 'sleep') as sleep:
            owner.wait_core('artificial')
        self.assertEqual(owner.process_identity.call_count, 2)
        sleep.assert_called_once_with(1)
        owner.command.assert_called_once()

    def observer_fixture(self):
        owner = sequence.Sequence.__new__(sequence.Sequence)
        owner.root = owner.workspace = self.root
        owner.cfg = {'protocol': 'realtime_choice_v1'}
        owner.pins = {'07_監視システム/watch.py': 'artificial_source'}
        owner.state = {'active': {'run_id': 'artificial'}}
        owner.save = Mock()
        path = self.root / 'runs/artificial/manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'status': 'RUNNING', 'pid': 1234}), encoding='utf-8')
        process = {'state': 'alive', 'pid': 1234, 'created': 111}
        monitor = {'state': 'alive', 'pid': 123, 'created': 222}
        target = {'status': 'RUNNING', 'target_id': 'artificial', 'pid': 1234,
                  'protocol': 'realtime_choice_v1', 'purpose': 'core', 'flags': [],
                  'source': str(path), 'state_sha256': sequence.digest(path),
                  'process': process, 'command_verified_binding': {'kind': 'direct', 'command_target_id': 'artificial'},
                  'observed_at_utc': datetime.now().astimezone().isoformat()}
        state = {'monitor_source_sha256': 'artificial_source', 'monitor_identity': monitor,
                 'targets': {str(path): target}}
        owner.command = Mock(return_value={'runtime': str(self.root), 'monitor_identity_matches': True,
                                          'monitor_process': monitor, 'observation_age_sec': 2})
        return owner, state, target

    def test_observer_binds_current_source_process_and_exact_core(self):
        owner, state, target = self.observer_fixture()
        (self.root / 'state.json').write_text(json.dumps(state), encoding='utf-8')
        self.assertTrue(owner.observer('artificial'))
        self.assertEqual(owner.state['active']['process_identity'], target['process'])
        target['process'] = dict(target['process'], created=333)
        (self.root / 'state.json').write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaises(RuntimeError):
            owner.observer('artificial')

    def test_observer_source_change_does_not_pass_fresh_status(self):
        owner, state, target = self.observer_fixture()
        state['monitor_source_sha256'] = 'another_version'
        (self.root / 'state.json').write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaises(RuntimeError):
            owner.observer()

    def test_observer_anomaly_or_stale_target_stops(self):
        owner, state, target = self.observer_fixture()
        for key, value in [('flags', ['process_command_mismatch']),
                           ('observed_at_utc', (datetime.now().astimezone() - timedelta(minutes=3)).isoformat())]:
            with self.subTest(key=key):
                changed = copy.deepcopy(state)
                changed['targets'][target['source']][key] = value
                (self.root / 'state.json').write_text(json.dumps(changed), encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    owner.observer('artificial')


if __name__ == '__main__':
    unittest.main()
