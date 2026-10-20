---
name: joso-jdrt-runner
description: Run, resume, independently validate, and record Joso City 08211 JDRT cells in registered series; also prepare technical probes for the registered choice series. Do not use for other municipalities.
---

# Joso JDRT Runner

Use the deterministic helper instead of rebuilding long shell commands or manually copying metrics.

Choose the helper that matches the registered series:

- Registered choice series (`realtime_choice_v1`): **technical preparation only for now** through `scripts/choice_technical.py`. Read [references/realtime_choice.md](references/realtime_choice.md). Core launch remains disabled until the complete registered READY gate is implemented and verified.
- Approved boundary-aligned B (`realtime_b_boundary_v2`, human proposal-1 approval 2026-10-16): `scripts/realtime_b_boundary_cell.py`. Read [references/realtime_b_boundary.md](references/realtime_b_boundary.md). This is the current 15-cell comparison; preserve the previous B eight records and HOLD without mixing them into it.
- Existing JDRT v2 core: `scripts/jdrt_cell.py`
- Realistic-series no-bus baseline REAL-R0: `scripts/real_r0_cell.py`
- Registered bounded-domain realtime-B (`realtime_b_v1`): `scripts/realtime_b_cell.py`. Read [references/realtime_b.md](references/realtime_b.md) before its first start. Never route this series through the legacy REAL-R0 helper.

## Model and token policy

- The deterministic helper, fixed inputs, SUMO, and independent validation determine the accepted research result. The model only orchestrates the workflow. Never change parameters, code, inputs, or acceptance gates to accommodate a smaller model.
- Preserve the user's selected model and reasoning setting. If asked to choose settings, use current official guidance and representative verified tasks; do not impose a universal reasoning level or an old model-based role split.
- On an unexpected status, `INVALID` or `FAILED`, orphan recovery, or SHA/accounting mismatch, stop subsequent runs. The current agent may investigate and perform authorized technical recovery. Never improvise parameter or acceptance-gate changes. Recommend escalation only for a concrete unresolved capability limit; a model label alone is not a stopping condition.
- A skill cannot switch its own model. Do not create or fork another task only to change models unless the user explicitly asks. Research-policy changes require the project decision process, regardless of model capability.
- Load `AGENTS.md`, the current section of `context.md`, and this file once at the start of a turn. Reuse that context for unchanged checks, keep progress messages compact, and do not read full logs or browse model documentation during a routine cell. Never omit the repository Fact-Forcing Gate.

Model selection follows the [official task-based model guidance](https://developers.openai.com/api/docs/guides/model-selection). Research acceptance remains determined by the fixed protocol and independent validation.

## Required loop

1. Read the repository `AGENTS.md` and current `context.md` as needed; reuse unchanged context. Apply the Fact-Forcing Gate at the scope defined in `AGENTS.md`, including run start, recovery, and formal recording. Read-only status/check/validation calls do not require repeating the four-item Gate.
2. Run `status`. If it reports a completed but unrecorded cell, run `record` before starting anything else.
3. Run at most one core cell. Use `start-next`; never start a second cell while a manifest is `RUNNING`.
4. Poll with `check --run-id ...`. Do not stream the full warning log into the conversation.
5. When the manifest is `COMPLETED`, run `validate --run-id ...`. Proceed only on `PASS`, then run `record --run-id ...`. `record` repeats the independent validation of SHA-256, CSV accounting, VKT, event count, SUMO errors, controller/observation counts, and zero-teleport gates before updating all required records.
6. Do not proceed to the next cell unless `record` returns `RECORDED` or `ALREADY_RECORDED` with validation `PASS`.
7. On `INVALID` or `FAILED`, stop. On an orphaned `RUNNING` manifest, confirm the recorded PID is absent and then use `recover` before creating a new run ID.

## Operational evidence

The v2 CLI appends timestamped command results, durations, and exceptions to `experiments/jdrt/driver_logs/operations.jsonl`. Keep run warnings/errors in the original SUMO and driver logs; classify them through independent validation rather than pasting full logs into Markdown. Record observed errors, diagnosis, fixes, verification, and unresolved limitations in the task record and progress report. Log a skill revision with affected files and checks; do not claim historical commands were automatically logged before this feature existed.

`status` requires both the experiment record and ledger entry before treating a completed cell as recorded. `record` repairs a missing ledger entry after independent validation and rolls back all six files on a caught write/verification failure. This is not crash-atomic across files: after a machine/process interruption, inspect all six records before restarting. Only one skill writer may operate at a time.

From the repository root, invoke the helper with:

```powershell
.\04_プログラム\venv\Scripts\python.exe .\.agents\skills\joso-jdrt-runner\scripts\jdrt_cell.py --project-root . status
```

For REAL-R0, invoke:

```powershell
.\04_プログラム\venv\Scripts\python.exe .\.agents\skills\joso-jdrt-runner\scripts\real_r0_cell.py --project-root . status
```

Use `--help` for the other subcommands. Read [references/workflow.md](references/workflow.md) only when diagnosing a stop, changing the workflow, or auditing what `record` writes.

## Authorized completion monitoring and final report

When the user authorizes completing all registered cells, repeat the one-cell transaction across turns: validate and record the current cell before starting the next. A request for monitoring can use a thread heartbeat; record its automation ID in the task record, avoid duplicate writers, and remain quiet when no meaningful state changes. An anomaly stops subsequent starts and requires diagnosis. Do not treat a heartbeat as permission to run an unregistered series.

After every registered v2 core cell is completed and recorded, run `scripts/jdrt_results.py --project-root .` with the project venv Python. It independently revalidates the full set and writes `06_研究結果/jdrt/JDRT-v2_全セル結果一覧.html`. It refuses incomplete, unrecorded, duplicate, or invalid sets before creating or replacing the file. The offline HTML includes all accepted cells, explicit denominators, technical checks, excluded same-version run history, and source SHA evidence. It does not combine other protocols. Open the result, update the task/current-state/index/progress records, notify completion, and pause the completion-monitor heartbeat after its work is finished.

## Boundaries

- Scope is only Joso City code `08211`, protocol `v2`, legacy `realistic_v1` REAL-R0, registered `realtime_b_v1`, human-approved `realtime_b_boundary_v2`, or registered `realtime_choice_v1` technical preparation, and their fixed Parameter Registries.
- Preserve v1 and all completed Phase 1-3/Scenario C outputs.
- Never modify `step_bus`, regenerate `gen_index.py`, or restore `output/` with Git.
- Never hardcode observed research results. Read them from immutable run artifacts.
- Do not make direction claims until all 20 core cells are validated and recorded.
- The helper does not automate research-policy changes, sensitivity design, final interpretation, or WEB3.
