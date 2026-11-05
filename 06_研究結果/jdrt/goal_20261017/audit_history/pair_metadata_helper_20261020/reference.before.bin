# Progress record policy (2026-10-20)

Current record_files has six documents and one ledger. Record concise daily bullets to the status Markdown first, then render its bounded progress region to HTML; include both in the journal, rollback and recovery. Historical six-file references below describe the previous contract. The process does not change research parameters or acceptance criteria.

# Registered choice-series preparation

`realtime_choice_v1` is registered by the final-goal delegation of 2026-10-17, with PAP `03_研究設計文書/jdrt/常総市JDRT_受付代替行動_PreAnalysisPlan_v1.md`. Read its state contract and detailed task as needed. Preserve old series and their run/code/input/ledger records. Do not route choice cells through another series CLI.

Current helper `scripts/choice_technical.py` permits **technical probes only**. Run with project venv Python from the root:

```powershell
.\04_プログラム\venv\Scripts\python.exe .agents/skills/joso-jdrt-runner/scripts/choice_technical.py --project-root . status
.\04_プログラム\venv\Scripts\python.exe .agents/skills/joso-jdrt-runner/scripts/choice_technical.py --project-root . probe --run-id <new-unique-id>
```

Choice toolchain pin (2026-10-20): set `JDRT_CHOICE_TOOLCHAIN_MANIFEST` in the calling process to the selected isolated control/patched bundle manifest. Core and READY require an explicit valid manifest; an absent selector retains installed-SUMO discovery only for technical compatibility. An explicit empty, missing, invalid or changed manifest never falls back. The choice-only resolver binds all bundle files (including controlled DLLs and Python sources), roles, provenance, manifest and its own source SHA, and rejects foreign loaded `traci`/`sumolib` modules. It does not change global environment settings or shared/old-series resolvers. Preserve source/fingerprint history: changed common-five or resolver/bundle bytes invalidate old suite, counterexample, smoke and READY evidence. This binding alone does not prove native-patch correctness or actual OS/external DLL load paths; verify the build/import/dependency proof before adopting a bundle. Schema, limits, source archives and artificial-file tests: [toolchain binding report](../../../../06_研究結果/jdrt/goal_20261017/choice_toolchain_binding_20261020.md). No real bundle was adopted by this revision.

Isolated bundle packaging: after the build owner independently confirms both target builds, custom versions, source/patch/compiler/dependency proof and static non-OS dependency closure, use `scripts/choice_package_toolchain.py`. Packaging does not grant research READY or run permission. Use separate new destinations for control and patched; existing or partially failed destinations are never reused.

```powershell
.\04_プログラム\venv\Scripts\python.exe -B .agents/skills/joso-jdrt-runner/scripts/choice_package_toolchain.py --source-tools <official-source-tools> --sumo <confirmed-sumo.exe> --netconvert <confirmed-netconvert.exe> --provenance <native_provenance.json> --tools-inventory <official_python_tools_inventory.json> --destination <new-path-under-04_プログラム/output/sumo/toolchains> --evidence <patch-or-additional-license-proof>
.\04_プログラム\venv\Scripts\python.exe -B .agents/skills/joso-jdrt-runner/scripts/choice_package_toolchain.py --verify-manifest <new-bundle/toolchain.json>
```

`--evidence` may repeat for additional patch/source/dependency/license evidence. The packager requires `isolated_native_provenance_v1` with terminal `isolated_native_build_v1`, the latest successful combined sumo/netconvert build, matching executable SHA/size, successful custom-version logs, and direct PE imports matching the proof. It accepts only its explicit Windows OS DLL allowlist and no delay imports; a non-OS DLL is a rejection, not an invitation to search PATH or copy an arbitrary DLL. Compiler/config/source archive and zlib dependency references are independently hashed. A complete `official_python_tools_inventory_v1` must bind all traci/sumolib files plus AUTHORS/LICENSE/NOTICE to the official source commit, equal to native proof `source_commit`. The original ZIP members are independently hashed and their selected file set must exactly match the inventory; missing/changed/extra sources, bytecode, symlinks and junctions are rejected. If the pristine source/tools or required proof is missing, return to the build owner; do not download/rebuild without authorization.

The bundle contains exact executable/Python/license bytes and verbatim native/tool inventory JSON, metadata/config/build/version logs and explicitly supplied attachments. Compiler binaries, static archives and the large official source ZIP remain SHA-checked references. Its `toolchain.json` uses the resolver's exact schema 1, four roles and all non-manifest file hashes. A post-creation failure preserves `FAILED.json` and all partial files; choose another destination. Freeze successful bundle bytes. Run the verification command in a fresh process: it resolves, actually imports traci/sumolib and fingerprints twice, verifies module paths against controlled files and rejects any newly added pyc/file. It starts no SUMO simulation and writes nothing to the bundle. Record the stdout verification outside the bundle.

After adoption, pass the same manifest selector in the process environment for every status/check/monitor/fixture/validate/preflight call (including child processes); do not change OS persistent settings, PATH or the global SUMO installation. Monitoring also computes a runtime fingerprint: omitting the selector can select installed SUMO and yield an incorrect SHA comparison. The parent records the adopted manifest path/SHA in current context and monitoring automation when adoption is actually authorized. Proof JSON, packaging and import verification do not substitute for native regression, the complete current suite/audit/all14 smokes or the new READY preflight.

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
