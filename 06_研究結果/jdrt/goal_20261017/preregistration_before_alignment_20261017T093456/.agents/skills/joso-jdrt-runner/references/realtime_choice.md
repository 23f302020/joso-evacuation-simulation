# Registered choice-series preparation

`realtime_choice_v1` is registered by the final-goal delegation of 2026-10-17, with PAP `03_研究設計文書/jdrt/常総市JDRT_受付代替行動_PreAnalysisPlan_v1.md`. Read its state contract and detailed task as needed. Preserve old series and their run/code/input/ledger records. Do not route choice cells through another series CLI.

Current helper `scripts/choice_technical.py` permits **technical probes only**. Run with project venv Python from the root:

```powershell
.\04_プログラム\venv\Scripts\python.exe .agents/skills/joso-jdrt-runner/scripts/choice_technical.py --project-root . status
.\04_プログラム\venv\Scripts\python.exe .agents/skills/joso-jdrt-runner/scripts/choice_technical.py --project-root . probe --run-id <new-unique-id>
```

For registered-setting **smoke only**, `scripts/realtime_choice_cell.py --project-root . status/check/smoke` is available. Smoke requires `--cell-id <registered-cell-id> --run-id <new-id>` and accepts `--end-sec` for its technical horizon. Read its output and check the same ID to completion. It has no core-start command yet. Never count a completed smoke as independently validated or formally recorded. A smoke fixture preserves complete selected private-vehicle crews and samples willing/non-willing Type3/4; its shortened readiness/cohort are explicitly technical, not the core input.

Use a new unique ID under the choice workspace `technical/`. Never reuse/overwrite a probe directory. Fixtures have synthetic roads/people and must never enter the research ledger. Log command, manifest PID/status, per-step positions/stops/transitions, errors/teleports/collisions, assertions and artifact hashes. Apply the project Fact-Forcing Gate before probe start. If still running at 15 minutes, inspect the same PID and progress via status and record the observation; do not restart because a tool observation times out. For a short probe, record completion without creating a duplicate heartbeat.

Probe failure is not a research-method failure: preserve the whole directory, diagnose and fix only the technical implementation, then use a new ID. No scripts/inputs edits while a core or technical SUMO is running. Stop downstream starts on unresolved failure.

Core execution remains unavailable until new executor/run validator, input independence, actual cancellation/timing cases, all14 settings smoke, six-file record transaction, common implementation SHA and preflight READY are implemented and verified. The existence of this reference or technical helper is not READY and cannot authorize a core launch. All70 accepted cells must share the registered implementation set; no old run or fixture reuse. Exits remain separate, no direction interpretation before all70.

Drive read-only and no external send/public update. At actual core readiness use a dedicated registered CLI and align the existing paused monitoring automation with the new series before a single core launch; do not silently resume the old series monitor.
