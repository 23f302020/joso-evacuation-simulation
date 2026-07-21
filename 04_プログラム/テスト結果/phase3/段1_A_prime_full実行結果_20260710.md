# Phase 3 段1：A'（シナリオA・teleport=-1）full実行結果（2026-07-10）

**対象**：常総市 08211・scenario full・`run_id: full_20260710T000934_fc2ca003`
**コード版**：`6106263 Scope git dirty state for run manifests`
**検証者**：Opus（実ファイル確認）／記録：Sonnet 5
**正本**：`開発メモ/方針判断_fable5/02_実行系是正/実行計画改訂_方針判断_fable5.md`（決定9〜16・改訂AC1〜AC10）、`開発メモ/方針判断_fable5/02_実行系是正/manifest_git_dirty_方針判断_fable5.md`（決定24〜30）
**状態**：**A'は完走。AC1は「不一致」。滞留479台の政策差／アーチファクト切り分けは Fable 5 の判断待ち（実行計画改訂メモ 留意点2・3）。**

---

## 1. 段0ゲート（4点）の結果

| ゲート項目 | 結果 | 根拠 |
|---|---|---|
| C1掃除コミット | `251d432 Record Phase 3 cleanup artifacts` | コード変更なし・文書/output差分のみ |
| C2是正コミット | `6106263 Scope git dirty state for run manifests` | `git_state()` を `git_dirty_repo`／`git_dirty_scripts`／`git_scope_path` 記録へ変更、A/Bの `git_state(PROGRAM_DIR, SCRIPT_DIR)` 引数統一、`git_state()` 単体テスト追加、日本語パスで `git_commit` が空になる問題も修正 |
| py_compile | PASS | |
| pytest | PASS | 49 collected / 49 passed |
| 10pct Aスモーク | PASS | 1,151台・全到着・`git_commit=6106263…`・`git_dirty_scripts=false`・`outputs` の `missing=[]`・sha256再計算一致 |
| B軽量スモーク | PASS | `conservation_ok=true`・fcd/tripinfo XML parse OK・sha256再計算一致・passenger/busログ時刻 ≤ fcd最終timestep |

→ **決定21の4点ゲートを通過**（決定28の C1→C2→ゲート→夜1 の順を満たす）。

## 2. A' full実行のマニフェスト検証（AC5第3改訂）

Opusが実ファイルで確認した値：

| 項目 | 値 |
|---|---|
| `run_id` | `full_20260710T000934_fc2ca003` |
| `phase` | `scenario_a` |
| `started_at` | 2026-07-10T00:09:34 |
| `ended_at` | 2026-07-10T00:56:10（**wall-clock 約47分**） |
| `git_commit` | `61062630f219cbdf3e578b83ee2a80af7e760124`（40桁hex・非空） |
| `git_dirty_scripts` | `False` |
| `git_dirty_repo` | `True`（診断情報・合否に使わない） |
| `git_scope_path` | `C:\Users\Ko_rr\OneDrive - stu.teikyo-u.ac.jp\研究室\4年次本研究\04_プログラム\scripts` |
| `outputs` のキー | `sumocfg`／`route_file`／`assignments`／`tripinfo`／`fcd`／`vehicle_log`／`closure_log`／`congestion_log`。`missing: true` は**0件** |
| `scenario_a_fcd.xml` | 最終timestep `time="21600.00"`・`</fcd-export>` まで閉じタグ完全（95.5MB） |

→ **AC5（第3改訂）の各条件を満たす。**

注記：実行後のリポジトリ未コミット差分は214件（`scripts/` 配下は0件）。改行churnの再発であり、`実行計画改訂_方針判断_fable5.md` 留意点1が予告したとおり**非合否の `git_dirty_repo` にのみ影響する**。実装者報告の「未コミット差分は `region_run_summary.csv` のみ」は、実測では214件（うち `region_run_summary.csv` 1件）であった。

## 3. A' の実行結果と旧R4との比較（AC1判定）

| 指標 | 旧R4（teleport=既定300秒・`archive_R4_20260705/`） | A'（teleport=-1・`run_id: full_20260710T000934_fc2ca003`） |
|---|---|---|
| vehicle_count | 9,569 | 9,569 |
| arrived_count | 9,569 | 9,090 |
| not_arrived_count | 0 | **479** |
| long_stopped_count | 102 | **4,026** |
| stranded_main_count | 0 | 479 |
| reroute_failed_count | 0 | 0 |
| departure_blocked_count | 0 | 0 |
| closure_event_count | 8 | 8 |
| final_closed_sumo_edge_count | 8,968 | 8,968 |
| 到着車の完了時間 mean／median／p90／max（秒） | 2,714／2,271／5,502／19,134 | 2,587／2,094／5,491／8,885 |

**AC1判定：不一致。** 改訂AC1は「arrived=9,569・not_arrived=0 なら床効果確定。不一致なら不一致値のままA'で再固定（旧値回帰禁止）。合否にかかわらずA'が正本」と定める。よって**A'を正本として再固定する**。旧R4の数値へ合わせる操作は禁止。

到着車の完了時間 max が旧19,134秒→A' 8,885秒と縮んでいる点について、事実として次を注記する（解釈は加えない）：A'では479台が到着しておらず、完了時間分布は到着車のみで集計されている。

## 4. 未到着479台の内訳（vehicle_log）

- 未到着479台のうち：`long_stopped` 479台（全数）／`stranded_main` 479台（全数）／`reroute_failed` 0台／`departure_blocked_by_closure` 0台
- 種別：自家用車 415台／救出走行 64台
- **到着した車両のうち `long_stopped` は 3,547台**（未到着479と合わせて `long_stopped_count` 4,026）

## 5. 滞留位置の切り分け材料（fcd最終timestep t=21,600秒）

Opusが `scenario_a_fcd.xml` の最終timestepから集計した事実：

- 走行中（＝未到着）479台。うち**速度0が475台**
- 滞留している distinct edge 数：**109本**
- 上位10 edge に集中する台数：148/479（**30.9%**）。上位は `12365#7`（21台）・`8570`（20台）・`290#8`（18台）・`52#3`（14台）・`290#11`（14台）・`12365#6`（14台）・`5316#1`（13台）・`52#4`（12台）・`52#12`（11台）・`265#6`（11台）
- 閉鎖SUMO edge 総数 8,968 との突合：滞留109 edge のうち閉鎖済みは **26本（23.9%）**。滞留車両ベースでは **94台（19.6%）が閉鎖edge上**、残り385台は非閉鎖edge上

> `実行計画改訂_方針判断_fable5.md` 留意点2（決定3由来）は「not_arrived が数百台規模で出た場合、それが『政策差』か『モデルアーチファクト』かを fcd の滞留位置で切り分けてから解釈すること（自動では判定しない）」と定める。同 留意点3 は「A' で not_arrived>0 が出た場合、床効果の記述を書き直し、long_stopped 102台の扱いを再判定する」と定める。**切り分けと再判定は Fable 5 の判断事項であり、本記録では判断しない。**

## 6. 実行コスト実測（決定9の前提との差）

- A' full の wall-clock は **約47分**（00:09:34→00:56:10）。
- 決定9は「R4'中断時の26分/sim 1,260秒」からの外挿で「1runあたり約3〜5時間・夜間12時間予算・12時間で進捗50%未満ならTraCI subscription化／libsumo化へ転換」を定めていた。
- **事実として実測47分はこの前提と乖離する。** 前提の見直し要否は Fable 5 の判断事項であり、本記録では判断しない。
