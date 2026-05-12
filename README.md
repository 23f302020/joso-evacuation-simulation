# 4年次本研究

**研究テーマ：** 河川氾濫時における自家用車避難とデマンド交通バス活用の比較シミュレーション ― 鬼怒川氾濫を事例として ―  
**最終更新：** 2026/05/12

---

## 研究概要

2015年9月の鬼怒川氾濫（茨城県常総市）を対象に、道路閉鎖を時系列で再現した上で
自家用車避難の経路・到達可否を可視化するシミュレーションを構築する。  
Phase 1（自家用車避難シナリオ）は **茨城県内41市区町村対応で完了**。  
Phase 2（SUMO交通シミュレーション）、Phase 3（バス比較）へ順次移行予定。

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
│   ├── 経過報告20260401.pptx
│   ├── 経過報告20260401coment.txt
│   ├── 経過報告20260422.md
│   └── 経過報告20260513.md      ← 最新（Phase 1 完了時点）
│
├── 02_情報調査/                  ← 各種調査結果
│   ├── J_実装前調査結果.md       ← データ取得・実装前調査の総括
│   ├── データカタログ.md
│   ├── データ取得状況_確認結果.md
│   ├── 氾濫データ調査_鬼怒川2015.md
│   ├── 浸水ナビAPI_ハイドログラフ取得結果.md
│   ├── 茨城県内拡張_必要データ調査.md
│   └── （その他 法制度・先行文献・ODPT・モデル仮定調査）
│
├── 03_研究設計文書/              ← 研究の前提・設計書
│   ├── 実装仕様書.md             ← Phase 1〜3 の実装仕様
│   ├── RQ・研究課題.md
│   ├── モデル仮定一覧.md
│   ├── 評価フレーム設計.md
│   ├── 論文構成_Phase1.md
│   ├── 論文構成_Phase2.md
│   ├── 論文構成_Phase3.md
│   └── （シーケンス図・データフロー図・ユースケース図 等）
│
├── 04_プログラム/                ← 実装ファイル本体
│   ├── scripts/                  ← Pythonスクリプト群
│   │   ├── config.py             ← 共通定数（CRS・閾値・パス等）
│   │   ├── c3_get_road_network.py← OSMnxで道路NW取得（常総市）
│   │   ├── e1_load_flood_data.py ← A31a GML + KML → 浸水ポリゴン
│   │   ├── i1_spatial_join.py    ← 浸水ポリゴン × 道路エッジ → 閉鎖候補
│   │   ├── i2_generate_closure.py← 時刻別道路閉鎖リスト生成
│   │   ├── i3_route_search.py    ← Dijkstra 避難ルート探索
│   │   ├── p1_city_road_network.py← 茨城県全41市区町村 道路NW取得
│   │   ├── city_scenario.py      ← 市別シナリオHTML生成（41市区町村）
│   │   ├── v2_scenario_route_simulation.py ← 常総市シナリオHTML生成
│   │   ├── gen_index.py          ← トップページ index.html 生成
│   │   └── gen_unified.py        ← 茨城県統合シミュレーション生成
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
│   ├── output/                   ← 生成済みHTML（.gitignore 対象）
│   │   ├── index.html            ← トップページ（市区町村選択UI）
│   │   ├── unified/              ← 茨城県41市区町村統合シミュレーション
│   │   ├── scenario_cities/      ← 市別シナリオHTML（41市区町村）
│   │   ├── scenario_v2/          ← 常総市単独シナリオ（参考）
│   │   ├── routes/               ← 実データ版時刻別ルートマップ
│   │   └── flood/                ← 浸水時系列マップ
│   │
│   ├── テスト結果_phase1/         ← Phase 1 各段階のテスト記録
│   │   ├── README.md             ← テスト結果の索引
│   │   ├── テスト結果_phase1_final_20260512.md
│   │   ├── テスト結果_t7到達不可分析_取手市_城里町.md
│   │   ├── テスト結果_対象外3市町村_除外理由分析.md
│   │   └── SUMO_TraCI実装メモ.md ← Phase 2 実装設計メモ
│   └── 環境・ツール記録.md
│
├── 05_タスク管理/                ← 進捗管理
│   ├── 実装タスク一覧.md         ← I系タスクの進捗（Phase 1〜3）
│   ├── 調査タスク一覧.md         ← J系調査タスク（全完了）
│   ├── 実装手順書_Phase1.md      ← Phase 1 スクリプト実行手順
│   └── 茨城県内拡張_市区町村別タスク.md ← 41市区町村のA31a確認結果
│
└── 06_研究結果/                  ← フェーズ別研究結果・成果物記録
    ├── phase1/
    │   ├── Phase1_研究結果.md    ← Phase 1 結果・考察・成果物一覧
    │   └── Phase1_成果物固定リスト.md ← Phase 1 成果物の固定方針・数値
    ├── phase2/
    │   └── Phase2_研究結果.md    ← Phase 2 結果（未着手）
    └── phase3/
        └── Phase3_研究結果.md    ← Phase 3 結果（未着手）
```

---

## 実装パイプライン（Phase 1）

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
  + GSI 避難所               city_scenario.py   scenario_route_simulation.html
  + 市別道路NW

[統合・インデックス]
  gen_unified.py              →   output/unified/
  gen_index.py                →   output/index.html
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
| **Phase 1** | 自家用車避難シナリオ（道路閉鎖 + Dijkstra ルート探索） | **完了** |
| Phase 2 | SUMO 交通シミュレーション（`i4_convert_sumo.py` 等） | 未着手 |
| Phase 3 | バス比較・集計・評価 | 未着手 |

### Phase 1 達成事項

- 実データ版（常総市・40出発地）：閉鎖タイムライン t0〜t7 の単調増加を実現
- 市別シナリオ：茨城県内**41市区町村** の HTML ページを生成（A31a 段階的閉鎖）
- 統合シミュレーション：全市区町村を1画面で確認できる統合ページ
- インデックス：市区町村選択 UI・対象外市区町村一覧を備えたトップページ
- 可視化改善：浸水ポリゴン格子・マスク矩形の重なりを修正

### 次フェーズへの優先タスク

1. `i4_convert_sumo.py` 実装（OSMnx → SUMO .net.xml 変換）
2. TraCI による道路閉鎖・車両エージェント制御（I-5〜6）
3. バスシミュレーション・比較・集計（I-7〜9）

---

## 技術スタック

| 用途 | ツール |
|------|--------|
| 道路ネットワーク | OSMnx + NetworkX |
| 空間解析 | GeoPandas + Shapely |
| ルート探索 | Dijkstra（JavaScript クライアントサイド） |
| 可視化 | Leaflet.js + CartoDB tiles |
| 交通シミュレーション | SUMO + TraCI（Phase 2 以降） |
| データ形式 | A31a GML（国土数値情報）, KML, GeoPackage, GraphML |

---

## 関連ファイル（研究室フォルダ内）

| ファイル | 場所 |
|---------|------|
| ODPTキー | `公共交通オープンデータ/交通オープンデータ開発者キー.txt` |
| 先行研究 | `3年次プレテーマ/経過報告/プレテーマ経過報告/` |
