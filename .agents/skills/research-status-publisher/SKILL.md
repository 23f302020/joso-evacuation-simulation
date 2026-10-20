---
name: research-status-publisher
description: Publish the existing Joso research status HTML to its existing Cloudflare Worker when the user explicitly requests publication.
---

# Research status publication

Use the project's [skill and agent operations](../../../05_タスク管理/スキル・エージェント運用.md) for invocation and delegation; the publication steps below remain the task-specific procedure.

This workflow is for `00_全体整理/現状把握_静的・動的シミュレーション整理.html` only.
Publication requires an explicit user request; research-monitoring authorization alone is insufficient.

1. Read the current source and `00_全体整理/公開用_cloudflare/wrangler.jsonc`. Confirm the existing Worker is `joso-research-status` and destination `https://joso-research-status.30k-012rei.workers.dev`. Since 2026-10-18 the deployed module is `status-worker.mjs`; `public/index.html` is the staged copy, not a separately uploaded directory.
2. Apply the repository Fact-Forcing Gate. Preserve the previous staged index and current remote HTML, with SHA-256 and time, under a new local `00_全体整理/公開用_cloudflare/deployment_history/<timestamp>/` directory outside `public`.
3. Copy the source bytes to `public/index.html`. Confirm `public` contains only that file, source/staged SHA equality, valid page anchors, no external asset dependency, and the existing public-host code disables local document links. Do not publish referenced repository files or run gen_index.py.
4. Run `scripts/prepare.py --check` to ensure source, staged HTML and generated module agree; omit `--check` to regenerate both from the source after preserving prior bytes. Load the Cloudflare and Wrangler skills. Run `wrangler deploy --dry-run`, then `wrangler deploy` when authenticated. If CLI authentication is unavailable, the connected Cloudflare execute API can upload the exact generated module via multipart PUT to `/accounts/{account_id}/workers/scripts/joso-research-status`, with `main_module=status-worker.mjs`, the existing compatibility date, and empty bindings. Discover the endpoint and current account/settings first. Do not request broad new OAuth scopes or use a temporary account. Preserve the result but never JWTs/tokens. A failed/timeout command must be inspected before retrying; never claim success without its receipt.
5. Fetch the published URL, require HTTP 200 and byte/SHA equality with the staged HTML, and inspect it in a browser for current status, page anchors, disabled local links, overflow and console errors. Preserve receipt/version ID and verification locally.
6. Record the deployment in the relevant task, decision log and progress report. State the explicit publication authorization and exact HTML scope. Return the public URL. Do not turn one deployment request into recurring publication permission.

Established 2026-10-18 after the second publication operation. The previous 2026-09-12 deployment procedure/config and public-host link handling are retained; this skill adds reusable source/history/remote verification without changing research methods.

2026-10-18 delivery change: Wrangler lacked credentials, and the connector asset-upload fetch returned Unauthorized. The same existing Worker was updated through its authorized module API instead. Its module returns the exact source bytes at `/`, redirects `/index.html` to `/`, and returns 404 for unrelated paths. Previous static-assets version `5b640e21-5f19-43b5-8990-1bb12200881a` remains available for rollback. Original staged/remote/config bytes are preserved in deployment_history/20261018T204646956. No research runtime/input change.
