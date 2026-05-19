# Phase 2 SUMO引用・再現性メモ

作成日：2026/05/19  
対象：Phase 2（SUMO/TraCIによる自家用車避難シミュレーション）

---

## 1. 目的

Phase 2で使用した交通流シミュレータ SUMO について、卒論本文・方法章・再現性説明に記載する情報を固定する。

---

## 2. 使用ツール

| 項目 | 固定内容 |
|---|---|
| シミュレータ | Eclipse SUMO |
| 使用バージョン | 1.26.0 |
| 確認コマンド | `sumo --version` |
| 確認日 | 2026/05/19 |
| Python連携 | `SUMO_HOME/tools` の `traci` / `sumolib` |
| 使用目的 | 道路ネットワーク上の車両走行、動的道路閉鎖、再経路探索、到着・未到着・混雑ログの出力 |

ローカル確認結果：

```text
Eclipse SUMO sumo 1.26.0
Build features: Windows-10.0.17763 AMD64 MSVC 19.29.30133.0 Release FMI Proj GUI FMT Intl SWIG Parquet Eigen
```

---

## 3. 導入方法

| 項目 | 内容 |
|---|---|
| 採用導入方法 | 公式Windows 64-bit MSIの管理展開 |
| 実際の `SUMO_HOME` | `C:\Users\Ko_rr\AppData\Local\Programs\sumo-1.26.0-msi-extract\PFiles\Eclipse\Sumo` |
| PATH | `%SUMO_HOME%\bin` をユーザーPATHへ追加 |
| Python API | `%SUMO_HOME%\tools` から `traci` / `sumolib` を読み込み |

通常のMSIサイレントインストールは exit code `1603` で失敗したため、同じMSIをユーザー領域へ管理展開した。  
実装スクリプトでは `p2_sumo_env.py` により、`SUMO_HOME` が現在プロセスへ引き継がれていない場合でも、今回の導入先を自動検出する。

---

## 4. 論文での引用方針

SUMO全体の説明では、公式ドキュメントが推奨する次の一般引用を用いる。

```text
Lopez, P. A., Behrisch, M., Bieker-Walz, L., Erdmann, J., Flötteröd, Y.-P.,
Hilbrich, R., Lücken, L., Rummel, J., Wagner, P., & Wiessner, E. (2018).
Microscopic Traffic Simulation using SUMO.
2018 21st International Conference on Intelligent Transportation Systems (ITSC),
2575-2582. https://doi.org/10.1109/ITSC.2018.8569938
```

使用バージョンを明示する場合は、SUMO 1.26.0のソフトウェアDOIも併記する。

```text
Alvarez Lopez, P., Banse, A., Barthauer, M., Behrisch, M., Couéraud, B.,
Erdmann, J., Flötteröd, Y.-P., Hilbrich, R., Nippold, R., & Wagner, P. (2026).
Simulation of Urban Mobility (SUMO) (1.26.0). Zenodo.
https://doi.org/10.5281/zenodo.13907886
```

参照元：

- SUMO Publications: https://sumo.dlr.de/daily/userdoc/Publications.html
- Eclipse SUMO About: https://sumo.dlr.de/about/

---

## 5. 卒論本文用の説明文案

本研究のPhase 2では、オープンソースの微視的交通流シミュレータ Eclipse SUMO 1.26.0を用いた。SUMOは個々の車両を道路ネットワーク上で明示的に扱えるため、避難車両の走行、道路閉鎖、再経路探索、到着状況、停止・低速状態を時系列で評価できる。PythonからはSUMO同梱のTraCIおよびsumolibを利用し、浸水時系列に応じて道路リンクを動的に閉鎖した。

---

## 6. 再現時の確認項目

| 確認 | 通過条件 |
|---|---|
| `sumo --version` | `Eclipse SUMO sumo 1.26.0` が表示される |
| `netconvert --version` | 1.26.0 が表示される |
| `SUMO_HOME` | SUMO導入先を指している |
| Python import | `traci` / `sumolib` が読み込める |
| ネットワーク | `joso.net.xml` が生成済み |
| edge対応 | Phase 1閉鎖edge 764件がすべてSUMO edgeへ対応する |
| 実行結果 | small / 10pct / full の評価CSVが生成される |

