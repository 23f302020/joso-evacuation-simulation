# Repeated monitoring and current-display synchronization

Use this reference for routine choice-series operations. Research inputs, the common-five implementation, and formal adoption gates are unchanged.

The user instructed on2026-10-18 that work repeated twice or more must be skillized; skills may subsequently be updated with a reason, source history, and relevant verification. Reuse an existing helper first and extend only a demonstrated gap. Do not create one skill per run or repeat long ad hoc shell/Python blocks.

## Model routing

- Routine monitoring, extraction and recording: request `gpt-6-luna` with `low` reasoning first. Use deterministic output rather than asking it to rederive research judgments.
- Research decisions, anomalies, complex implementation and mathematical interpretation: request `gpt-6.1-sol` with `high` reasoning, as the user explicitly selected.
- A routine worker stops downstream actions and returns raw evidence on exceptions, missing checks, SHA/accounting mismatches or unexplained status. It does not repair the model, reinterpret acceptance, or omit observations.
- When the available spawn tool requires it, use a fresh brief (`fork_turns=none`) with explicit model/effort. Give only necessary artifacts. Record requested settings separately from actual backend identity if the latter is not observable. Editing a role file or this skill does not switch the parent chat's running model.
- Only one actor owns start/record/recovery. Other workers may read or edit specifically assigned independent documentation. A second model's agreement is not independent source recomputation.

Project role files: `.codex/agents/jdrt-recorder.toml` and `.codex/agents/jdrt-reasoner.toml`. The current tool's explicit spawn arguments remain the observable execution request.

## Same-cell monitoring

From the project root and venv Python:

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_monitor.py --run-id <current-id>
```

This calls the dedicated skill `check`, observes PID/progress, recomputes whole-person accounting and current input/common-five/archived-READY hashes, and records log sizes, native Error prefixes and storage. It writes a unique timestamped report plus goal/workspace operations and workspace monitoring JSONL. It never starts/rejects/recovers/validates/adopts a cell. Error prefixes and progress snapshots are not formal validation. A nonempty anomaly list blocks subsequent starts pending high-reasoning diagnosis.

Inspect the same live process at15minutes and each15minutes thereafter; preserve completion observed earlier. A tool observation timeout is not a stopped process. The old goal-folder G5 monitoring entry is a compatibility wrapper; update the canonical skill script.

## Technical fixture suite monitoring

`choice_monitor.py` remains core-only. For `technical/<suite-id>` and its actual fixture child, use:

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_technical_monitor.py --suite-id <suite-id>
```

The helper reads the archived factory's `CASES` order and actual child directories, then calls the dedicated `check --run-id <actual-child>` on that same ID. Suite `progress.json` describes the last completed case; it can still name a calibration child after the next child has failed. Never substitute that completed child for the actual one. PID creation time and command distinguish an absent process, matching process, reused PID and ambiguous identity. Missing evidence, SHA/accounting inconsistencies and failed suites produce a preserved observation with anomalies and nonzero exit; no downstream start is permitted.

The report keeps child heartbeat simulation time/timestamp separate from the latest raw actor and event times. A terminal heartbeat at zero does not mean the failure occurred at simulation zero. It also records native Error/Warning prefixes, input/common-five/archive/output SHA evidence, whole-person accounting, storage and the original-file inventory. Open gzip streams may be partial; partial evidence is flagged and never treated as final. Observations append once with the same timestamp and content to goal operations, workspace operations and workspace monitoring JSONL. The dedicated `check` also writes its ordinary operation entry. No start/recover/reject/validate/record/adoption command is exposed.

Revision2026-10-19: added the separate technical monitor after repeated manual fixture monitoring demonstrated the core helper's incompatible purpose/path gate. The prior core helper is unchanged. Seven temporary-evidence unit checks and CLI help passed; one observation of preserved `wf26101801` selected actual `c26`, distinguished heartbeat0 from raw52.5 and confirmed all77 original files unchanged. The three observation entries are unique and identical. Evidence/history: `06_研究結果/jdrt/goal_20261017/技術監視skill_20261019.md` and its linked observation/synchronization audit. These are technical observations, not formal research acceptance.

## Current display

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_sync_status.py
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_sync_status.py --apply
```

Preview first after a helper revision; ordinary later calls may apply directly when the prerequisites and scope are unchanged. The helper takes the existing writer lock, derives formal counts from the dedicated controller, preserves old document/checkpoint bytes, and updates only the current summary in context/md/html plus the CH-M1 display. It preserves acceptance markers and creates none. Caught write failures restore its changed targets; machine interruption still requires inspection. Partial formal records or a mismatched current summary fail closed.

Formal `validate → record → status` remains in `realtime_choice_cell.py`. The sync helper never substitutes for six-file record, changes acceptance, or treats an unrecorded completed run as adopted. Do not edit the frozen common-five to add routine logging while a core is running.


## Repeated 14-setting technical smoke sequence

Use the canonical skill script for the registered-seed 14-setting sequence; the old goal-folder entry is now an argv-preserving compatibility wrapper. This helper runs only technical `smoke` followed by independent `validate --purpose smoke`; it never launches or records a research core. It requires a current independent suite/counterexample audit whose implementation hashes match the frozen current implementation, then checks those five implementation hashes before every setting. Any command or evidence failure leaves its run/state and stops the sequence. Do not reuse a prefix or resume a failed sequence under the same IDs.

From the project root, after the current suite and counterexample audit pass, choose a fresh unique prefix and run:

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_smoke_sequence.py --prefix <fresh-unique-prefix> --audit 06_研究結果/jdrt/goal_20261017/<current-audit>.json
```

The helper writes `<prefix>_smoke_sequence.json` in `06_研究結果/jdrt/goal_20261017/`, plus command stdout/stderr and goal operations; its active item records the current smoke/validate PID and run ID. Check that state and the same PID if the helper has not exited. Preserve failed state and artifacts; a new attempt gets a new prefix. The audit, current implementation SHA set, and all14 smoke receipts are technical prerequisites only. Continue to the separate new preflight; this helper does not make the series READY or permit core start. Do not run it while a research core or another technical SUMO process is active.

## Complete technical revalidation after an implementation freeze

Use `scripts/choice_revalidate.py` for the repeated complete fixture → independent counterexample audit → registered-setting smoke sequence → preflight workflow. It calls the existing CLIs in that order; it does not launch a core, adopt a run, recover a failure, or retry/resume a stopped attempt. It requires authorization for technical simulation starts and the project Fact-Forcing Gate. Never start it alongside another SUMO workflow. Freeze the common five first; this helper binds their current hashes and its calling sources before launching any stage.

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_revalidate.py --project-root . --suite-id <fresh-suite-id> --smoke-prefix <fresh-prefix>
```

The exclusive parent state is `06_研究結果/jdrt/goal_20261017/<suite-id>_revalidate.json`. A global `choice_revalidate.lock` prevents another instance, and `<prefix>_revalidate_reservation.json` permanently reserves the prefix even if fixture/audit fails. Use fresh IDs after failure; retain the prior state and artifacts. The parent records commands, PID, source hashes, start/end, exit codes, result paths/hashes, active stage and monitor paths. Nonzero exit, unexpected JSON shape, source/artifact change, ambiguous audit output or missing prerequisite stops downstream starts.

The fixture CLI returns the suite manifest object. The audit prints an object containing a counterexample **list**, omitting its fixture component list; it does not print a report path. The parent selects exactly one newly created `正式検証器_表会計候補_*.json` by before/after directory difference, compares it to stdout and binds its SHA. It never assumes a list has `.get`, selects the latest arbitrary report, or substitutes an old PASS.

While a child runs, the parent waits in 15-second observation intervals and saves the same PID and timestamp. At 15 minutes and every 15 minutes thereafter, inspect the same parent state and `active.monitor_paths`: fixture manifest/progress includes the current child ID; smoke sequence state includes the active smoke/validate ID/PID. The existing `choice_technical.py --project-root . status` and `realtime_choice_cell.py --project-root . check --run-id <active-id>` remain available. An observation timeout never kills/restarts the child. An interrupted wait preserves the lock and child PID for explicit inspection; there is no automatic recovery. A completed parent reports technical preflight evidence only; the dedicated core CLI still enforces its separate start gates.
