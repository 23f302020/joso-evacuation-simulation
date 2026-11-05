# Repeated monitoring and current-display synchronization

Use this reference for routine choice-series operations. Research inputs, the common-five implementation, and formal adoption gates are unchanged.

The user instructed on2026-10-18 that work repeated twice or more must be skillized; skills may subsequently be updated with a reason, source history, and relevant verification. Reuse an existing helper first and extend only a demonstrated gap. Do not create one skill per run or repeat long ad hoc shell/Python blocks.

## Roles and delegation

Use [the project's skill and agent operations](../../../../05_タスク管理/スキル・エージェント運用.md), section 0 and the research-agent table, for current role/model routing, authorization, single-writer ownership and requested-vs-observed backend records. This reference owns the concrete helper commands below, not a second model policy. Role TOML files remain executable settings; update their consistency with the canonical operations document when the user changes a role.

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

For an isolated-build display, supply the canonical monitor report to both preview and apply: append `--build-observation <project-local-nativebuild-report.json>` to each command above. The helper verifies the archived state snapshot bytes/SHA, false adoption/READY/start gates and observed PID identities. It displays that report's timestamp/status/phase as a point observation, including an old or terminal report; it does not query or assert present liveness. Compile completion never establishes native-regression PASS or READY. Without a build report, existing technical HOLD/READY=false remains in place.

Preview first after a helper revision; ordinary later calls may apply directly when the prerequisites and scope are unchanged. The helper takes the existing writer lock, derives formal counts from the dedicated controller, and rechecks status/source/evidence before apply. On the first migration it identifies the existing top context/Markdown summaries and two dedicated HTML current asides, archives exact original bytes, and installs bounded current markers. Later edits use those markers with separate text/HTML encoding; mismatched manual summary text is no longer a whole-file replacement dependency. It updates only current regions/dates and CH-M1's final display cell. BOM, existing EOL (including CRCRLF), all other bytes and acceptance markers are preserved; NUL or ambiguous markers fail closed. Checkpoint JSON accepts UTF-8 BOM, derives current implementation SHA from the real configuration, marks old READY/PASS evidence STALE/historical, and retains the complete previous checkpoint by content-addressed history. Same-report reapply is byte-idempotent. Writes use atomic replacement, readback and caught-failure rollback; machine interruption still requires inspection. Partial formal records stop before display changes. No publication occurs. Revision evidence and temporary-document tests: [2026-10-20 sync report](../../../../06_研究結果/jdrt/goal_20261017/choice_sync_status_20261020.md).

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


## Isolated native-build monitoring

For a running isolated native build, use its absolute `build_state.json` path with the dedicated read-only helper:

```powershell
.\04_プログラム\venv\Scripts\python.exe -X utf8 .agents/skills/joso-jdrt-runner/scripts/choice_native_build_monitor.py --state <absolute-build-state-json>
```

The native build is not a research run: its `isolated_native_build_v1` state is the primary build record, and a research execution manifest is not applicable. The helper checks the actual build schema, status, phase and prohibited-simulation flags. It independently queries CIM for the same owner and active child PIDs and compares process creation milliseconds, command, executable and parent PID. Missing creation/command evidence remains unknown; a numerical PID alone never establishes a live build. An absent, reused, mismatched or unknown nonterminal identity, partial JSON, unsupported schema or terminal FAILED preserves an anomaly and a nonzero exit. Stop downstream action for diagnosis.

Each invocation saves an exact state-byte snapshot, state SHA, UTC/JST observation time, state update time, bounded log tails and bytes, disk capacity/free bytes, and one identical observation entry in goal operations and workspace operations/monitoring JSONL. Whole log SHA is recorded only for terminal states; a live state/log may legitimately change during a read. The three entries are point observations, not continuous coverage. Inspect the same build after15minutes and every15minutes thereafter; the orchestrator's frequent state updates (currently approximately20seconds) do not supply independent15minute observations. The helper reports a previous helper observation and its elapsed gap when available; the first invocation cannot establish earlier coverage.

This helper exposes no start, kill, rebuild, recovery, research CLI check, validation or record action. It never accesses research input data and never makes native regression verified, research core READY or downstream start permitted, including when the build reports COMPLETED. Those require their separate technical gates. A routine fresh brief may request `gpt-6-luna`/`low` with `fork_turns=none`, providing only the helper path, absolute build state and current observation; record requested settings separately from any independently observable backend identity. Exceptions return preserved evidence to the judgment worker and do not authorize repairs.

Revision2026-10-20: isolated build state/CIM monitoring was added after repeated manual observations. Prior helpers and the existing reference text are preserved. Nine temporary/mock checks cover creation matches, PID reuse/absence/unknown identity, command mismatch, failure/completion boundaries, partial JSON, read-only source bytes and identical three-JSONL recording. A real Windows CIM observation matched both owner and child. Reason, old reference/SHA, checks and observation linkage: `06_研究結果/jdrt/goal_20261017/nativebuild監視skill_20261020.md`.

Native-build status revision2026-10-20: the actual orchestrator emits terminal `FAILED_PRESERVED` on failure and `COMPILED_VERSION_CHECKED_NOT_SIMULATED` after compile/version checks. Both are recognized terminal states and receive whole-log SHA; preserved failure emits its own failure anomaly, while absent terminal owner/child is legal. The success status grants no simulation, native-regression verification, core READY, adoption or downstream permission. Unknown status remains fail closed. Source-state evidence, pre-edit helper/reference bytes and12 unit checks are archived in `audit_history/native_build_monitor_skill_20261020/failed_preserved_revision/`. Prior RUNNING observations remain valid and unchanged.

Routine document append safeguard (observed2026-10-20): use apply_patch or byte append so existing bytes/EOL/BOM remain unchanged. A routine PowerShell document update introduced a NUL and rewrote old EOL; avoid whole-file readText/writeText or Set-Content resaves, and never let Markdown backticks be interpreted inside PowerShell double-quoted strings. Check the added region for NUL/trailing whitespace and inspect the scoped diff. This is a document-writing check, not a research acceptance gate.
