# Phase 3 実装・評価フロー図

> 作成日：2026-07-20  
> 対象：常総市先行、シナリオA/B反復比較、S10感度分析  
> 正本値：`04_プログラム/output/sumo/regions/08211/evaluation/phase3r_e1_*`  
> 注意：本図は「デマンド交通車両を転用した固定ルート避難シャトル」を扱う。需要応答型の動的配車ではない。

---

## 1. Phase 1〜3の接続

```mermaid
flowchart LR
    P1["Phase 1<br/>浸水・道路閉鎖・静的経路"]
    P2["Phase 2<br/>SUMO変換・TraCI動的閉鎖"]
    PREP["Phase 3前処理<br/>Type1〜4・救出走行・バス候補"]
    A["シナリオA<br/>自家用車＋救出走行"]
    B["シナリオB<br/>自家用車＋削減後救出走行<br/>＋固定ルートバス"]
    EVAL["A/B反復評価<br/>完了率を正式判定"]

    P1 --> P2 --> PREP
    PREP --> A & B
    A & B --> EVAL
```

Phase 1の到達不可人口、Phase 2の旧単一run、Phase 3の人換算完了率は単位・実行条件が異なる。図中で連続した処理として接続するが、結果値を直接比較しない。

---

## 2. シナリオ生成と実行フロー

```mermaid
flowchart TD
    INPUT["入力<br/>SUMO道路NW・閉鎖時系列・人口・安全避難所"]
    TYPE["p2_phase3_prep_agents.py<br/>Type1〜4・バス需要候補"]
    ACCOUNT["p3_bus_accounting.py<br/>救出走行会計"]

    subgraph SA["シナリオA"]
        AROUTE["scenario_a.rou.xml<br/>9,569台"]
        ARUN["p2_traci_closure.py<br/>A側3seed・teleport=-1"]
        AOUT["tripinfo・車両/閉鎖/FCDログ"]
    end

    subgraph SB["シナリオB"]
        BSCN["p3_bus_scenario.py<br/>固定ルート・バス5台"]
        REDUCE["補正後バス到着125人<br/>救出走行54台を外生削減"]
        BROUTE["scenario_b route/config<br/>9,515台＋バス"]
        BRUN["p2_traci_bus.py<br/>B側5seed・teleport=-1"]
        BOUT["tripinfo・乗降/便ログ・bus summary"]
    end

    INPUT --> TYPE --> ACCOUNT
    ACCOUNT --> AROUTE --> ARUN --> AOUT
    ACCOUNT --> BSCN --> REDUCE --> BROUTE --> BRUN --> BOUT
```

> **会計上の注意：** raw系列は救出走行到着人数換算とバス到着人数を加算する。保守系列は二重計上上限を考慮してバス人数を124.2人でcapする。個人IDによる重複除去ではないため、raw・保守を必ず併記する。

---

## 3. 正本ゲートと反復評価

```mermaid
flowchart TD
    RUN["各run成果物<br/>tripinfo・summary・run ID"]
    GATE{"正本ゲート<br/>完走・会計保存・seed・route・script整合"}
    RETRACT["撤回・履歴領域<br/>正式結果へ接続しない"]
    METRICS["phase3r_e1_replicate_metrics.csv<br/>A3run＋B5run"]
    SIGNS["A3×B5の15組合せ<br/>raw・保守の差と符号"]
    CHECK{"15組すべてで<br/>符号が一貫?"}
    NULL["方向差は検出されない<br/>現行結論"]
    CANDIDATE["方向主張候補<br/>追加検証が必要"]

    RUN --> GATE
    GATE -- "不合格" --> RETRACT
    GATE -- "合格" --> METRICS --> SIGNS --> CHECK
    CHECK -- "いいえ" --> NULL
    CHECK -- "はい" --> CANDIDATE
```

15組合せは8runを組み替えた差であり、15個の独立runではない。符号一貫性は研究内の事前判定規則であり、統計的有意差・同等性を直接示すものではない。

---

## 4. 指標の分岐

```mermaid
flowchart LR
    METRICS["正本8run"]
    MAIN["正式判定<br/>Type3/4完了率"]
    TIME["補助<br/>完了時間ECDF"]
    DEMAND["B側絶対実績<br/>バス輸送人数・需要充足率"]
    EQUITY["診断のみ<br/>Type別公平性"]
    CONG["未統合<br/>Phase 3渋滞A/B比較"]
    RESULT["研究結果<br/>方向差は検出されない"]

    METRICS --> MAIN --> RESULT
    METRICS --> TIME
    METRICS --> DEMAND
    METRICS --> EQUITY
    METRICS -. "最終成果物未作成" .-> CONG
```

| 指標 | 現在の扱い | 図表上の表現 |
|---|---|---|
| Type3/4完了率 | 正式A/B判定 | 点推定とゼロをまたぐ全組合せ範囲を併記 |
| 完了時間 | 補助 | A3・B5のECDF。A#2は到着者条件付きであることを注記 |
| 需要充足率 | B側絶対実績 | 候補247人基準とType3/4総人口3,255人基準を併記 |
| Type別公平性 | 診断 | demographicな優劣を示さない |
| 渋滞 | 未統合 | A/B効果図を作らず、未評価と明示 |

---

## 5. 感度分析と成果物

```mermaid
flowchart TD
    BASE["基本条件<br/>バス5台・B側5seed"]
    S10["S10<br/>バス10台・同じB側5seed"]
    RAW["raw<br/>正10・負5<br/>最大102.01%"]
    CONS["保守<br/>正8・負7<br/>最大97.15%"]
    STOP["両系列とも符号非一貫<br/>S系終了・3台run取消"]
    CSV["評価CSV/JSON"]
    XLSX["Phase 3 Excel"]
    HTML["phase3.html / phase3_viz.html"]
    DOC["E3本文・論文図表"]

    BASE --> S10
    S10 --> RAW & CONS
    RAW & CONS --> STOP
    STOP --> CSV --> XLSX & HTML & DOC
```

S10のraw完了率102.01%は、救出走行削減54台を固定した増車のみ設計に伴う二重計上バイアスを含む。図ではraw値を削除せず、保守値と注意書きを必ず併記する。

---

## 6. 図表作成時の禁止事項

- 点推定+1.23%ptだけを棒グラフで強調しない。
- 正13・負2を多数決として「Bが優位」と読ませない。
- B#1やA#2を外れ値として除外しない。
- A3×B5の15組を15独立runと表記しない。
- 完了時間ECDFを未到着者を含む無条件分布として扱わない。
- 現run数だけで統計的な二峰性を実証したと表現しない。
- Phase 2のteleport有効結果とPhase 3のteleport無効結果を同条件で比較しない。

