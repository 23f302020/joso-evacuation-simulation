"""Fault-injection checks using copies of the registered local records."""

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "jdrt_cell", PROJECT / ".agents/skills/joso-jdrt-runner/scripts/jdrt_cell.py"
)
cell = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cell)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = [
            cell.PARAMETERS_REL, cell.FULL_RECORD_REL, cell.TASKS_REL,
            cell.CONTEXT_REL, cell.DECISIONS_REL, cell.PROGRESS_REL, cell.LEDGER_REL,
        ]
        for relative in self.paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / relative, target)
        entries = [json.loads(line) for line in (self.root / cell.LEDGER_REL).read_text(encoding="utf-8").splitlines() if line.strip()]
        self.result = max(entries, key=lambda entry: entry["core_index"])
        self.manifests = cell._matching_manifests(PROJECT, cell._sha256(PROJECT / cell.PARAMETERS_REL))
        self.manifest_patch = patch.object(cell, "_matching_manifests", return_value=self.manifests)
        self.manifest_patch.start()
        self.addCleanup(self.manifest_patch.stop)

    def remove_ledger_entry(self):
        path = self.root / cell.LEDGER_REL
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(line for line in lines if json.loads(line)["run_id"] != self.result["run_id"]) + "\n", encoding="utf-8")

    def snapshot(self):
        return {relative: (self.root / relative).read_bytes() for relative in self.paths}

    def test_complete_record_is_idempotent(self):
        before = self.snapshot()
        self.assertEqual(cell._update_documents(self.root, self.result)["record_status"], "ALREADY_RECORDED")
        self.assertEqual(before, self.snapshot())

    def test_missing_ledger_blocks_start_and_is_repaired_without_duplicate_detail(self):
        self.remove_ledger_entry()
        self.assertIn(self.result["run_id"], [item["run_id"] for item in cell.status(self.root)["completed_unrecorded"]])
        with self.assertRaisesRegex(RuntimeError, "record completed cell first"):
            cell.start_next(self.root)
        detail = (self.root / cell.FULL_RECORD_REL).read_bytes()
        self.assertEqual(cell._update_documents(self.root, self.result)["record_status"], "RECORDED")
        self.assertEqual(detail, (self.root / cell.FULL_RECORD_REL).read_bytes())
        self.assertIn(self.result["run_id"], cell._recorded_ids(self.root))
        self.assertEqual(cell._update_documents(self.root, self.result)["record_status"], "ALREADY_RECORDED")

    def test_ledger_write_failure_restores_documents_and_ledger_bytes(self):
        self.remove_ledger_entry()
        context = self.root / cell.CONTEXT_REL
        context.write_bytes(context.read_bytes().replace(self.result["run_id"].encode(), b"missing_record_identifier"))
        before = self.snapshot()
        original_write = cell._atomic_write
        failed = False

        def fail_once(path, text):
            nonlocal failed
            if path == self.root / cell.LEDGER_REL and not failed:
                failed = True
                raise OSError("injected ledger write failure")
            original_write(path, text)

        with patch.object(cell, "_atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "injected ledger"):
                cell._update_documents(self.root, self.result)
        self.assertTrue(failed)
        self.assertEqual(before, self.snapshot())

    def test_absent_ledger_is_created(self):
        (self.root / cell.LEDGER_REL).unlink()
        cell._update_documents(self.root, self.result)
        self.assertIn(self.result["run_id"], cell._recorded_ids(self.root))

    def test_historical_backfill_does_not_rewind_current_documents(self):
        first = cell._cells(cell._json(PROJECT / cell.PARAMETERS_REL))[0]
        manifest = cell._completed_by_cell(self.manifests)[first]
        result = cell.validate_run(PROJECT, manifest["run_id"])
        self.assertEqual(result["validation"], "PASS")
        before = {path: (self.root / path).read_bytes() for path in self.paths if path != cell.LEDGER_REL}
        cell._update_documents(self.root, result)
        after = {path: (self.root / path).read_bytes() for path in before}
        self.assertEqual(before, after)
        self.assertIn(result["run_id"], cell._recorded_ids(self.root))

    def test_operation_log_preserves_result_and_failure(self):
        failure = {"error_type": "RuntimeError", "error": "injected diagnostic failure"}
        for result in [self.result, failure]:
            cell._log_operation(self.root, "validate", self.result["run_id"], time.monotonic(), result)
        entries = [json.loads(line) for line in (self.root / cell.DRIVER_LOGS_REL / "operations.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["result"] for item in entries], [self.result, failure])
        self.assertTrue(all(item["recorded_at"] and item["elapsed_sec"] >= 0 for item in entries))

    def test_check_ignores_incomplete_event_line(self):
        source = PROJECT / cell.RUNS_REL / self.result["run_id"]
        target = self.root / cell.RUNS_REL / self.result["run_id"]
        target.mkdir(parents=True)
        shutil.copyfile(source / "manifest.json", target / "manifest.json")
        lines = (source / "events.jsonl").read_bytes().splitlines()[:2]
        (target / "events.jsonl").write_bytes(b"\n".join(lines) + b'\n{"unfinished":')
        result = cell.check_run(self.root, self.result["run_id"])
        self.assertEqual(result["observed_event_count"], len(lines))
        self.assertEqual(result["last_event_sim_time_sec"], json.loads(lines[-1])["sim_time_sec"])


if __name__ == "__main__":
    unittest.main()
