# Phase 2 実装フロー図

作成日：2026/05/14  
最終更新：2026/07/20（実行と評価の分離、teleport条件を追記）
対象：常総市実データ版 / シナリオA（自家用車のみ）

---

## 1. 実装全体フロー

```mermaid
flowchart TD
    START["Phase 1成果物"]
    GML["joso_road_network.graphml"]
    CLOSURE["road_closure_timeline.json"]
    ORIGIN["origin_points.csv"]
    SHELTER["shelters.csv"]

    NET1["GraphML属性確認"]
    NET2["OSM XMLへ変換\njoso.osm.xml"]
    NET3["netconvert\njoso.net.xml"]
    NET4["SUMO-GUI/netedit確認"]

    MAP1["SUMO edge一覧抽出"]
    MAP2["Phase 1閉鎖edge一覧抽出"]
    MAP3["edge_id_mapping.csv生成"]
    MAP4{"閉鎖対象edgeの\n未対応が0件?"}

    DER1["time_mapping_sumo.csv"]
    DER2["shelters_safety.csv"]
    DER3["agent_origins_10pct.csv"]
    SNAP["出発地・避難所をSUMO edgeへスナップ"]

    ROUTE["scenario_a_small.rou.xml\nscenario_a_small.sumocfg"]
    RUN0["閉鎖なし小規模走行確認"]
    TRACI["TraCI動的閉鎖\np2_traci_closure.py"]
    RUN1["小規模→1/10→全量"]

    OUT1["vehicle_log.csv"]
    OUT2["closure_log.csv"]
    OUT3["congestion_log.csv"]
    OUT0["tripinfo.xml"]
    EVAL["p2_evaluate_results.py\n実行ログを評価CSVへ集約"]
    OUT4["evacuation_summary.csv"]
    OUT5["phase1_phase2_comparison.csv"]
    INDEX["Phase別 index.html 更新"]

    START --> GML
    START --> CLOSURE
    START --> ORIGIN
    START --> SHELTER

    GML --> NET1 --> NET2 --> NET3 --> NET4
    NET3 --> MAP1
    CLOSURE --> MAP2
    MAP1 --> MAP3
    MAP2 --> MAP3 --> MAP4
    MAP4 -- "いいえ" --> MAP3
    MAP4 -- "はい" --> DER1

    SHELTER --> DER2
    ORIGIN --> DER3
    DER1 --> TRACI
    DER2 --> SNAP
    DER3 --> SNAP
    NET3 --> SNAP
    SNAP --> ROUTE --> RUN0 --> TRACI --> RUN1

    TRACI --> OUT1
    TRACI --> OUT2
    TRACI --> OUT3
    TRACI --> OUT0
    RUN1 --> EVAL
    OUT0 --> EVAL
    OUT1 --> EVAL
    OUT2 --> EVAL
    OUT3 --> EVAL
    EVAL --> OUT4
    OUT4 --> OUT5
    OUT1 --> OUT5
    OUT2 --> OUT5
    OUT3 --> OUT5
    OUT5 --> INDEX
```

---

## 2. 派生データの関係

```mermaid
flowchart LR
    subgraph PHASE1["Phase 1 出力"]
        G["joso_road_network.graphml"]
        E["road_closure_timeline.json"]
        O["origin_points.csv"]
        S["shelters.csv"]
    end

    subgraph SUMO_NET["SUMOネットワーク"]
        OSM["joso.osm.xml"]
        NET["joso.net.xml"]
        EDGES["sumo_edges.csv"]
    end

    subgraph DERIVED["Phase 2 派生データ"]
        TIME["time_mapping_sumo.csv"]
        SAFE["shelters_safety.csv"]
        AGENT["agent_origins_10pct.csv"]
        MAP["edge_id_mapping.csv"]
        CLOSE["closure_timeline_sumo.json"]
        OSNAP["agent_origins_sumo.csv"]
        SSNAP["shelters_sumo.csv"]
    end

    subgraph SCENARIO["SUMOシナリオ"]
        ROUTE["scenario_a_*.rou.xml"]
        CFG["scenario_a_*.sumocfg"]
    end

    subgraph RESULTS["実行結果"]
        VEH["vehicle_log.csv"]
        CLO["closure_log.csv"]
        CONG["congestion_log.csv"]
        TRIP["tripinfo.xml"]
    end

    subgraph EVALUATION["評価"]
        EVAL["p2_evaluate_results.py"]
        SUM["evacuation_summary.csv"]
        COMP["phase1_phase2_comparison.csv"]
    end

    G --> OSM --> NET --> EDGES
    E --> MAP
    EDGES --> MAP --> CLOSE
    E --> CLOSE
    O --> AGENT --> OSNAP
    S --> SAFE --> SSNAP
    NET --> OSNAP
    NET --> SSNAP
    TIME --> CLOSE
    OSNAP --> ROUTE
    SSNAP --> ROUTE
    NET --> CFG
    ROUTE --> CFG
    CFG --> VEH
    CLOSE --> CLO
    CFG --> CONG
    CFG --> TRIP
    VEH & CLO & CONG & TRIP --> EVAL
    EVAL --> SUM
    SUM --> COMP
```

---

## 3. 実装ゲート

```mermaid
flowchart TD
    A["SUMO 1.26.0確認済み"] --> B{"joso.net.xml生成成功?"}
    B -- "いいえ" --> B_FIX["GraphML→OSM変換方針を修正"]
    B -- "はい" --> C{"閉鎖edge対応率100%?"}
    C -- "いいえ" --> C_FIX["edge_id_mapping.csvを修正"]
    C -- "はい" --> D{"安全避難所が1件以上?"}
    D -- "いいえ" --> D_FIX["避難所安全性判定を確認"]
    D -- "はい" --> E{"出発地・避難所スナップ成功?"}
    E -- "いいえ" --> E_FIX["snap距離・対象edgeを確認"]
    E -- "はい" --> F["小規模SUMO走行"]
    F --> G{"閉鎖なしで到着確認?"}
    G -- "いいえ" --> G_FIX["route/configを修正"]
    G -- "はい" --> H{"teleport条件を\n実行記録に固定した?"}
    H -- "いいえ" --> H_FIX["sumocfg・実行ログへ\ntime-to-teleportを記録"]
    H -- "はい" --> I["TraCI動的閉鎖へ進む"]
```

> **条件の区別：** Phase 2で固定した旧small/10pct/full結果はSUMO既定のteleport 300秒を含む。Phase 3の比較正本A/Bは`time-to-teleport=-1`で実行している。両者を同一条件の結果として接続しない。
