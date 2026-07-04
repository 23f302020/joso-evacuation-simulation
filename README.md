# 4年次本研究

**研究テーマ：** 河川氾濫時における自家用車避難とデマンド交通バス活用の比較シミュレーション ― 鬼怒川氾濫を事例として ―  
**最終更新：** 2026/05/19

---

## 研究概要

2015年9月の鬼怒川氾濫（茨城県常総市）を対象に、道路閉鎖を時系列で再現した上で
自家用車避難の経路・到達可否を可視化するシミュレーションを構築する。  
Phase 1（自家用車避難 静的ルート探索）は **茨城県内41市区町村対応で完了**。  
Phase 2（SUMO/TraCI 交通シミュレーション）は **全41市区町村対応で完了**。  
Phase 3（バス比較）へ移行中。

---

## フォルダ構成

```
4年次本研究/
│
├── README.md                    ← このファイル
├── CLAUDE.md                    ← Claude Code 向けプロジェクト指示書
├── AGENTS.md                    ← エージェント作業ログ
├── 00_全体整理/                  ← 迷った時に見るファイル索引
│   └── README.md                 ← 重要ファイル・成果物・ディレクトリの案内
│
├── 01_経過報告/                  ← 指導教員への報告資料
│   ├── 経過報告2026XXXX.md       ← 日付別レポート（時系列）
│   └── 発表資料/                 ← pptx・中間発表スライド一式
│
├── 02_情報調査/                  ← 各種調査結果（テーマ別サブフォルダ）
│   ├── データソース/            ← データカタログ・取得状況・照合
│   ├── 氾濫・浸水/              ← 鬼怒川氾濫・浸水ナビAPI調査
│   ├── 交通・地域/              ← ODPT・常総市基礎・人口メッシュ
│   ├── 制度・文献/              ← 避難制度・先行文献
│   └── 経緯・振り返り/          ← J_実装前調査結果ほか
│
├── 03_研究設計文書/              ← 研究の前提・設計書
│   ├── 共通設計/                ← 実装仕様書・RQ・モデル仮定・評価フレーム・用語・文献
│   ├── 図表・UML/               ← データフロー図・シーケンス図・ファイル構造図・ユースケース図
│   ├── ChatBot/                 ← RAG導入記録
│   └── phase1/ phase2/ phase3/  ← 各フェーズ固有の設計・論文用文書
│
├── 04_プログラム/                ← 実装ファイル本体
│   ├── scripts/                  ← Pythonスクリプト群
│   │   ├── config.py             ← 共通定数（CRS・閾値・パス等）
│   │   ├── e1_load_flood_data.py ← A31a GML + KML → 浸水ポリゴン
│   │   ├── i1_spatial_join.py    ← 浸水ポリゴン × 道路エッジ → 閉鎖候補
│   │   ├── i2_generate_closure.py← 時刻別道路閉鎖リスト生成
│   │   ├── i3_route_search.py    ← Dijkstra 避難ルート探索
│   │   ├── p1_city_road_network.py← 茨城県全41市区町村 道路NW取得
│   │   ├── city_scenario.py      ← 市別シナリオHTML生成（41市区町村）
│   │   ├── v2_scenario_route_simulation.py ← 常総市シナリオHTML生成
│   │   ├── gen_index.py          ← トップページ index.html 生成
│   │   ├── gen_unified.py        ← 茨城県統合シミュレーション生成
│   │   │
│   │   ├── p2_sumo_env.py        ← SUMO環境検出ユーティリティ
│   │   ├── p2_sumo_network.py    ← GraphML → OSM XML → SUMO net.xml 変換
│   │   ├── p2_sumo_mapping.py    ← Phase 1 edge ID と SUMO edge ID の対応
│   │   ├── p2_sumo_snap.py       ← 出発地・避難所の SUMO edge スナップ
│   │   ├── p2_derived_data.py    ← 派生データ生成（時間軸・安全避難所・車両台数）
│   │   ├── p2_sumo_scenario.py   ← route/config XML 生成
│   │   ├── p2_traci_closure.py   ← TraCI 動的道路閉鎖シミュレーション
│   │   ├── p2_evaluate_results.py← 評価CSV・Phase 1/2 比較表生成
│   │   ├── p2_fcd_to_json.py     ← FCD XML → JS変数ファイル変換・可視化HTML生成
│   │   ├── p2_region_inventory.py← 全域拡張対象リスト・入力棚卸し生成
│   │   ├── p2_region_pipeline.py ← 市区町村別 SUMO パイプライン実行器
│   │   ├── p2_build_phase2_excel.py← Phase 2 評価 Excel（8シート）生成
│   │   ├── p2_phase3_prep_agents.py← 出発地エージェント属性分類（Type1〜4）
│   │   └── c3_get_road_network.py← OSMnxで道路NW取得（常総市）
│   │
│   ├── data/                     ← 入力データ（再ダウンロード可能）
│   │   ├── flood_kml/            ← GSI KML 8時点（鬼怒川2015）
│   │   ├── flood_hazard_a31/     ← A31a GML 国管理(08_10)・県管理(08_20)
│   │   ├── admin_boundary/       ← N03 茨城県行政区域（2015年版）
│   │   ├── shelters/             ← GSI 緊急避難場所（洪水対応・茨城県全域）
│   │   ├── population_mesh/      ← 250mメッシュ人口（T001178）
│   │   ├── suiboumap/            ← 浸水ナビ BP030 ハイドログラフ
│   │   └── vehicle_stats/        ← 自家用車統計
│   │
│   ├── output/                   ← 生成済み成果物（.gitignore 対象）
│   │   ├── index.html            ← トップページ（Phase 1/2/3 別）
│   │   ├── unified/              ← 茨城県41市区町村統合シミュレーション
│   │   ├── scenario_cities/      ← 市別シナリオHTML（41市区町村）
│   │   ├── scenario_v2/          ← 常総市単独シナリオ（参考）
│   │   ├── routes/               ← 実データ版時刻別ルートマップ
│   │   ├── flood/                ← 浸水時系列マップ
│   │   └── sumo/                 ← Phase 2 SUMO 成果物
│   │       ├── network/          ← 常総市 SUMO ネットワーク（joso.net.xml）
│   │       ├── derived/          ← 派生データ（edge対応・スナップ・時間軸）
│   │       ├── scenarios/        ← route/config XML（small/10pct/full）
│   │       ├── results/          ← TraCI 実行結果・FCD XML
│   │       ├── evaluation/       ← 評価CSV・Phase 1/2 比較CSV
│   │       ├── viz/              ← FCD 可視化（sumo_viz.html・JS変数ファイル）
│   │       └── regions/          ← 全41市区町村別 SUMO 成果物
│   │           ├── _management/  ← 対象リスト・棚卸し・バッチ状態管理CSV
│   │           └── {city_code}/  ← 市区町村別 network/derived/scenarios/results
│   │
│   ├── テスト結果_phase1/         ← Phase 1 テスト記録
│   │   └── README.md             ← テスト結果の索引
│   ├── テスト結果_phase2.md       ← Phase 2 常総市テスト記録
│   └── テスト結果_phase2_region.md← Phase 2 全域拡張テスト記録
│
├── 05_タスク管理/                ← 進捗管理
│   ├── 実装タスク一覧.md         ← I系タスクの進捗（Phase 1〜3）
│   ├── 調査タスク一覧.md         ← J系調査タスク（全完了）
│   ├── 実装手順書_Phase1.md      ← Phase 1 スクリプト実行手順
│   ├── phase2/                   ← Phase 2 タスク管理
│   │   ├── Phase2_実装タスク管理.md ← マイルストーン・サブタスク管理
│   │   ├── Phase2_詳細タスク管理.md ← 詳細設計・実装タスク
│   │   └── Phase2_判断事項一覧.md  ← 採用判断の記録
│   └── phase3/                   ← Phase 3 タスク管理
│       ├── Phase3_詳細タスク管理.md ← Phase 3 詳細設計・実装タスク
│       ├── Phase3_実装タスク管理.md ← マイルストーン・サブタスク管理
│       └── Phase3_判断事項一覧.md  ← 採用判断の記録
│
└── 06_研究結果/                  ← フェーズ別研究結果・成果物記録
    ├── phase1/
    │   ├── Phase1_研究結果.md
    │   └── Phase1_成果物固定リスト.md
    ├── phase2/
    │   ├── Phase2_研究結果.md         ← Phase 2 定量結果（完了・固定済み）
    │   ├── Phase2_評価表テンプレート.md
    │   ├── Phase2_成果物固定リスト.md  ← Phase 2 成果物の確定リスト
    │   ├── Phase2_先生コメント対応表.md← 指導教員コメントへの対応記録
    │   ├── Phase2_試行設定比較表.md    ← small/10pct/full 試行設定の比較
    │   ├── Phase2_比較基準固定.md      ← Phase 3 比較のベースライン定義
    │   ├── Phase2_考察本文案.md        ← Phase 2 考察ドラフト
    │   ├── Phase2_限界と今後の課題.md  ← 既知の限界・課題整理
    │   ├── Phase2_最終検証チェックリスト.md
    │   ├── Phase2_SUMO結果説明.md
    │   ├── Phase1_Phase2比較解釈.md   ← 静的 vs 動的の比較解釈
    │   └── Phase3前_エージェント4タイプ前処理結果.md
    └── phase3/
        └── Phase3_研究結果.md    ← Phase 3 結果（未着手）
```

---

## 実装パイプライン

### Phase 1（完了）

```
[データ取得]                        [中間成果物]
  A31a GML (08_10/08_20)
  GSI KML 8時点               →   flood_polygons.pkl
  N03 行政区域               e1_load_flood_data.py

  OSM 道路NW（osmnx）
  41市区町村                  →   {code}_road_network.graphml
  p1_city_road_network.py          {code}_edges.gpkg

[閉鎖生成]
  浸水ポリゴン × 道路エッジ   →   closure_edges.pkl
  i1_spatial_join.py               closure_timeline.json
  i2_generate_closure.py

[ルート探索（常総市実データ版）]
  Dijkstra（累積閉鎖）        →   evacuation_routes_t*.html
  i3_route_search.py

[市別シナリオ（茨城県41市区町村）]
  A31a 段階的閉鎖             →   scenario_cities/{code}/
  city_scenario.py                 scenario_route_simulation.html

[統合・インデックス]
  gen_unified.py              →   output/unified/
  gen_index.py                →   output/index.html
```

### Phase 2（完了）

```
[SUMO ネットワーク変換]
  GraphML → OSM XML → net.xml
  p2_sumo_network.py          →   joso.net.xml / {city_code}.net.xml

[edge 対応・派生データ]
  p2_sumo_mapping.py          →   edge_id_mapping.csv
  p2_derived_data.py          →   time_mapping_sumo.csv
  p2_sumo_snap.py                  agent_origins_sumo.csv / shelters_sumo.csv

[TraCI 動的閉鎖シミュレーション]
  p2_sumo_scenario.py         →   *.rou.xml / *.sumocfg
  p2_traci_closure.py         →   *_traci_summary.json / *_vehicle_log.csv

[評価・可視化]
  p2_evaluate_results.py      →   evacuation_summary.csv
                                   phase1_phase2_comparison.csv
  p2_fcd_to_json.py           →   vehicles_*.js / closures.js / sumo_viz.html

[全域拡張（41市区町村）]
  p2_region_inventory.py      →   phase2_region_targets.csv
  p2_region_pipeline.py       →   regions/{city_code}/ 成果物一式
                                   evacuation_summary_by_municipality.csv
                                   sumo/regions/index.html
```

---

## 使用データ

| データ | 用途 | パス |
|--------|------|------|
| GSI KML 8時点 | 鬼怒川2015実データ 浸水範囲 | `data/flood_kml/D1-No917_joso/` |
| A31a-24_08_10 GML | 国管理河川 浸水想定（那珂川・鬼怒川水系） | `data/flood_hazard_a31/A31a-24_08_10_GML/` |
| A31a-24_08_20 GML | 都道府県管理河川 浸水想定 | `data/flood_hazard_a31/A31a-24_08_20_GML/` |
| N03-20150101 茨城県 | 市区町村行政区域境界（2015年版） | `data/admin_boundary/N03-150101_08_GML/` |
| GSI 緊急避難場所（2号） | 洪水対応避難所（茨城県全44市区町村） | `data/shelters/gsi_designated_shelters_ibaraki_20260331/` |
| 250mメッシュ人口 T001178 | 出発地点（人口メッシュ重心） | `data/population_mesh/5歳階級別人口250メッシュ_茨城/` |
| 浸水ナビ BP030 | 破堤点ハイドログラフ（参考） | `data/suiboumap/hydrograph_origins_BP030.json` |

---

## データ管理

`04_プログラム/data/` 配下の入力データは、国土数値情報・国土地理院・e-Stat 等から再取得できる生データであり、Git では追跡しない。  
取得元、配置先、利用条件は `04_プログラム/data/manifest.csv` に整理し、自動取得できるZIPは次のコマンドで取得・展開する。

```powershell
cd 04_プログラム
python scripts/download_data.py
```

手動取得が必要なデータは `04_プログラム/data/README.md` の一覧に従って配置する。

---

## シミュレーション対象市区町村（41市区町村）

茨城県内44市区町村のうち、A31a 浸水想定区域ポリゴンが境界内に存在する41市区町村を対象。

**対象外（A31a 境界内0件 · 3市区町村）**

| 市区町村 | 理由 |
|---------|------|
| 鹿嶋市 | 太平洋・北浦汽水域。河川洪水浸水想定なし |
| 神栖市 | 利根川河口・太平洋沿岸。利根川系 A31a 未収録 |
| 東海村 | 海岸段丘台地。那珂川浸水想定が市境170m外止まり |

> 五霞町は利根川・渡良瀬川合流部に位置し、A31a 08_20 の境界±500mバッファで
> 501ポリゴンを取得してシナリオ生成済み（2026/05/11 昇格）。

---

## フェーズ別進捗

| Phase | 内容 | 状態 |
|-------|------|------|
| **Phase 1** | 自家用車避難シナリオ（道路閉鎖 + Dijkstra ルート探索、41市区町村） | **完了** |
| **Phase 2** | SUMO/TraCI 交通シミュレーション（41市区町村 small/10pct 完了） | **完了** |
| Phase 3 | バス比較・集計・評価 | 未着手 |

### Phase 1 達成事項

- 実データ版（常総市・40出発地）：閉鎖タイムライン t0〜t7 の単調増加を実現
- 市別シナリオ：茨城県内**41市区町村** の HTML ページを生成（A31a 段階的閉鎖）
- 統合シミュレーション：全市区町村を1画面で確認できる統合ページ
- インデックス：市区町村選択 UI・対象外市区町村一覧を備えたトップページ

### Phase 2 達成事項

- 常総市 SUMO ネットワーク変換・TraCI 動的道路閉鎖シミュレーション（small/10pct/full）
- FCD 出力・Leaflet.js 車両走行アニメーション（`sumo_viz.html`、small/10pct シナリオ切替 UI）
- 全 41 市区町村の small/10pct 完了（逃げ遅れ合計 0）
- full は代表 6 市区町村（守谷市・那珂市・行方市・大洗町・美浦村・五霞町）で実行
- 市区町村別評価 CSV（41行）・Phase 1/2 比較 CSV（164行）・全域 SUMO 結果 HTML 生成

### Phase 3 への優先タスク

1. バス設定仕様固定（シナリオ B 仮定値確定）
2. 常総市 small シナリオ B（バス混在）の SUMO 実装
3. シナリオ A/B 比較 CSV・評価指標算出
4. Phase 2 本文ドラフト（第3〜4章）・SUMO 引用情報整理

---

## 技術スタック

| 用途 | ツール |
|------|--------|
| 道路ネットワーク | OSMnx + NetworkX |
| 空間解析 | GeoPandas + Shapely |
| ルート探索（Phase 1） | Dijkstra（JavaScript クライアントサイド） |
| 交通シミュレーション（Phase 2） | SUMO 1.26.0 + TraCI |
| 可視化 | Leaflet.js + OpenStreetMap tiles |
| データ形式 | A31a GML（国土数値情報）, KML, GeoPackage, GraphML |

---

## ライセンス

研究コードとドキュメントは MIT License とする。外部データは各配布元の利用規約に従う。

---

## 関連ファイル（研究室フォルダ内）

| ファイル | 場所 |
|---------|------|
| ODPTキー | `公共交通オープンデータ/交通オープンデータ開発者キー.txt` |
| 先行研究 | `3年次プレテーマ/経過報告/プレテーマ経過報告/` |
