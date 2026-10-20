# Registered choice-series preparation

`realtime_choice_v1` is registered by the final-goal delegation of 2026-10-17, with PAP `03_研究設計文書/jdrt/常総市JDRT_受付代替行動_PreAnalysisPlan_v1.md`. Read its state contract and detailed task as needed. Preserve old series and their run/code/input/ledger records. Do not route choice cells through another series CLI.

Current helper `scripts/choice_technical.py` permits **technical probes only**. Run with project venv Python from the root:

```powershell
.\04_プログラム\venv\Scripts\python.exe .agents/skills/joso-jdrt-runner/scripts/choice_technical.py --project-root . status
.\04_プログラム\venv\Scripts\python.exe .agents/skills/joso-jdrt-runner/scripts/choice_technical.py --project-root . probe --run-id <new-unique-id>
```

For controller integration cases, use `choice_technical.py --project-root . fixture --run-id <new-id>`.
This creates artificial diamond/long-edge roads and case-specific inputs under unique `technical/` IDs,
then invokes the same `run(..., purpose='fixture')` controller. The fixture protocol is
`realtime_choice_fixture_v1`, forbids research adoption, and cannot be supplied to core/smoke mode.
`--case <name>` is for a failed-case diagnosis; READY requires the complete current suite, not isolated passes.
Cases force successful/over-budget walk rerouting, the 3000m conservative stop, reverse walk,
pickup/boarding/alighting closure, finite forecast-only rejection and offset/no-forecast cases,
shared capacity/separate exit and the unfinished service horizon. Inspect parent progress and child
`execution/manifest.json`, preserve any failure, and do not edit runtime/inputs during the suite.
The current suite also forces a forward car cycle/backward no-route case and private-car closure detouring.
Per-step actors use `after_step_before_control`; `snapshot_actor_observations.csv.gz` uses
`after_control_before_step` and is the source for road reaggregation. Retain actual route index/version,
native edge-vehicle membership and the arrival-tail distance evidence. A complete synthetic-suite PASS
is technical evidence only; it is never a research record or a substitute for all14 current setting smokes.

For registered-setting smoke, use `scripts/realtime_choice_cell.py --project-root . smoke --cell-id <registered-cell-id> --run-id <new-id>` with optional `--end-sec`. Read its output and check the same ID to completion. Never count a completed smoke as independently validated or formally recorded. A smoke fixture preserves complete selected private-vehicle crews and samples willing/non-willing Type3/4; its shortened readiness/cohort are explicitly technical, not the core input.

Validation uses `realtime_choice_cell.py --project-root . validate --run-id <id> --purpose smoke` (or `fixture`/`core`). It checks current bytes and writes outside the run. A technical PASS always has `core_adoption_permitted=false` and `technical_ready=false`; it cannot enter the research ledger. Core acceptance additionally requires its archived READY receipt and all current primary evidence. Changing any of the common five implementation files invalidates previous current-suite/smoke receipts; retain them as history and freeze the complete implementation before the final suite/all14 sequence.

The synthetic suite additionally derives pickup deadline equality/prior boarding and internal cancellation boundaries from its own earlier native CSVs. It includes a calibration turn, safe-external waiting after internal cancellation, and removal when the next external closes. Deliberate graph-time underprediction is fixture-only and is SHA-bound with its timing sources. Research waiting parameters are unchanged. Preserve failed suites, including evaluator failures, and use a new suite ID.

Use a new unique ID under the choice workspace `technical/`. Never reuse/overwrite a probe directory. Fixtures have synthetic roads/people and must never enter the research ledger. Log command, manifest PID/status, per-step positions/stops/transitions, errors/teleports/collisions, assertions and artifact hashes. Apply the project Fact-Forcing Gate before probe start. If still running at 15 minutes, inspect the same PID and progress via status and record the observation; do not restart because a tool observation times out. For a short probe, record completion without creating a duplicate heartbeat.

Probe failure is not a research-method failure: preserve the whole directory, diagnose and fix only the technical implementation, then use a new ID. No scripts/inputs edits while a core or technical SUMO is running. Stop downstream starts on unresolved failure.

After the complete current suite, counterexample audit and all14 independently validated smokes, run `realtime_choice_cell.py --project-root . preflight --suite-id <suite> --counterexamples <local-report-path>`. It reruns input/unit checks and binds the source/artifact/report/runtime hashes. A missing/failed/stale prerequisite prevents READY. The technical report is preserved even on failure. Capacity uses a disclosed empirical full-population/horizon projection with fourfold headroom and 5GiB additional reserve; all-remaining projection is reported separately. Before every next start, recheck the one-run reserve. This does not guarantee all70 fit; on insufficient capacity stop and preserve outputs without reducing observations or deleting runs.

Core loop: `status → start-next --run-id <new-short-id> → check --run-id <id> → validate --run-id <id> → record --run-id <id> → status`. Start-next reserves only the next registered cell and launches a detached project-Python child with hidden Windows execution. Do not invoke its internal `execute` directly. An unrecorded complete core, pending record journal, orphan launch/RUNNING, undiagnosed failure, foreign RUNNING or native process blocks the next start. All70 accepted cells must share the registered implementation set; no old run or fixture reuse. Exits remain separate, no direction interpretation before all70.

Recovery requires a recorded reason. Use `recover --run-id ... --reason ...` for an orphan RUNNING, `reject` for a stopped unacceptable run, `recover-launch` for an abandoned pre-manifest launch, `recover-record --transaction-id ... --reason ...` for PREPARED six-file rollback, and `recover-writer --reason ...` for an orphan writer lock. Confirm native/owner processes are absent. Preserve original manifests/state and observed record bytes. A six-file target with unrelated edits is not automatically overwritten. These are recovery operations, not permission to ignore failed acceptance checks.

Drive read-only and no external send/public update. At actual core readiness use a dedicated registered CLI and align the existing paused monitoring automation with the new series before a single core launch; do not silently resume the old series monitor.
