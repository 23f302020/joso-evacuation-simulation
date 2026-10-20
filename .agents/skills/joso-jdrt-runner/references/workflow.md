# Joso JDRT v2 workflow contract

> Historical completed-series contract below. From 2026-10-20, daily progress goes to the status HTML and details to the push commit-message body; see SKILL.md. Do not execute legacy record writers against the old progress Markdown. Current choice recording uses the registry HTML target.

## REAL-R0 extension

The realistic-series no-bus baseline uses `04_プログラム/config/jdrt_realistic_parameters_v1.json` and `scripts/real_r0_cell.py`. It follows the same one-cell transaction: `status` → `start-next` → `check` → `record`. Its immutable outputs are stored separately under `experiments/jdrt_realistic/runs`, so it neither imports nor modifies JDRT v2 cells.

REAL-R0 fixes the existing Scenario C 15% reference-assumption person ledger (21,539 people), retains 7,960 private cars and 3,231 walkers, and fixes bus/rescue vehicles at zero. `record` independently rechecks registered input/output SHA-256, engine accounting, row counts, zero bus/rescue vehicles, SUMO teleport/collision absence, and the generated 60-second edge congestion table.

## Authoritative inputs

- Current state: `context.md`
- Parameters: `04_プログラム/config/jdrt_parameters_v2.json`
- Input registry: `04_プログラム/config/jdrt_input_sources_v1.json`
- Runner: `04_プログラム/scripts/jdrt/full_run.py`
- Experiment record: `05_タスク管理/jdrt/JDRT-v2_full実験記録.md`

The helper derives seeds and scenario order from the v2 parameter file. The order is primary baseline, supporting scenarios in registry order, then primary proposal. It never imports a v1 result into the v2 completed set.

## One-cell transaction

`start-next` performs the existing runner's preflight and starts one detached Windows process. It writes only a new immutable run directory plus compact driver logs/state. It refuses to run if a prior completed cell has not been recorded or any v2 manifest remains `RUNNING`.

`record` is the commit point. It refuses anything except `COMPLETED`, `summary.valid=true`, and a full independent validation PASS. It is idempotent by run ID and updates these records together:

1. `05_タスク管理/jdrt/JDRT-v2_full実験記録.md`
2. `05_タスク管理/jdrt/JDRT_実装タスク管理.md`
3. `context.md`
4. `00_全体整理/決定ログ.md`
5. `01_経過報告/経過報告2026年08月/経過報告20260826.md`
6. `05_タスク管理/jdrt/JDRT-v2_セル検証台帳.jsonl`

All five documents and the ledger are included in the same rollback scope. On a caught write or verification failure, the helper restores their original bytes (or removes a newly created ledger). `ALREADY_RECORDED` requires the run ID in all five documents and the ledger. A missing ledger entry can be repaired without duplicating the experiment detail. `status` detects a missing ledger entry and blocks the next start.

This is rollback on caught exceptions, not crash-atomic filesystem storage. A power loss, forced process termination, persistent filesystem failure, or simultaneous writer requires inspection and repair before another start. Do not run multiple recording commands concurrently.

For an older cell already included in the full experiment record, with a later accepted cell also present, missing-ledger repair preserves all five documents byte-for-byte. Historical task/current-state summaries may only name the most recent cell, so historical idempotency uses the accepted full-record entry and ledger. Independent validation still runs before every repair; never infer acceptance from a ledger entry alone.

## Operation and change evidence

The v2 CLI appends each command's timestamp with timezone, elapsed seconds, run ID, result, and exception type/message to `driver_logs/operations.jsonl`. Original driver stdout/stderr and per-run SUMO logs remain separate. An operation-log write failure is surfaced; inspect whether a start or record already took effect before retrying.

Record skill changes and diagnosis in the JDRT task record and progress report, linking to primary logs. The JSONL log covers commands after the logging feature was installed; do not backdate earlier commands. Regression checks live in `tests/test_recording.py` and use temporary copies of local registered records for idempotency, missing-ledger recovery, next-start blocking, write-failure rollback, and operation evidence.

`check` includes the driver-state start date, number of complete event lines observed, and last event's simulation time/type. The v2 manifest does not provide a start timestamp; do not invent one. Ignore an incomplete trailing line while the runner writes. The last event time is an event observation, not a live SUMO clock or evidence of a hang; long periods without controller events can be normal.

## Validation gates

The optional `scripts/jdrt_results.py` report command reads the parameter registry's complete cell set and requires matching completed/recorded counts, no running or unrecorded cells, final-cell synchronization across the five documents, and an independent validation PASS for every cell. It generates one offline HTML only after those checks. It includes source manifest/config/ledger/full-record/generator SHA-256 values and the validated metrics; it leaves existing output untouched when collection fails. Tests in `tests/test_results.py` check incomplete-set refusal, output preservation, measured-row coverage, rate denominators, and escaping.

- parameter SHA: 1/1
- registered input SHA: 8/8 and equal to the manifest
- manifest output SHA: every listed output
- event row count and SHA
- person total and Type 3/4 evacuated counts
- request total and completed/stranded counts
- total and empty DRT VKT recalculated from vehicle CSV
- warning, error, and handled route-rejection counts recalculated from the SUMO error log
- expected controller and technical-observation counts derived from the parameter file
- `teleport_count`, collision teleport, gridlock teleport, and unhandled error counts all zero

Warnings and controller-caught route rejections remain auditable observations. A run is accepted only when every error is accounted for and the unhandled count is zero.

## Recovery

Use `check` first. `recover` requires a skill-created state file, a `RUNNING` manifest, and an absent recorded PID. It calls the repository's existing `finalize_interrupted_run`, preserving the partial event count and SHA as a `FAILED` run. Start a replacement only after recovery.

## Official design basis

OpenAI's skill guidance recommends a focused job, concise trigger description, progressive disclosure, imperative steps with explicit inputs and outputs, and scripts when deterministic behavior or external tooling is needed. The official page also documents repository-scoped skills under `.agents/skills`.

- https://learn.chatgpt.com/codex/build-skills
