# Native stage距離差の数値再構成と検証器修正

2026-10-20。研究正式0/70、READY=false。技術fixtureだけの診断。

`walkDistance()`は、全外部edge区間の補正長をE、全junctionの端点間推定長をJ、通過済みinternalの蓄積長をIとして、初期にはE+J、I>0になるとE+Iを返す。`Person::getStage().length`はこの値へ委譲する。固定した計画長とlive getterは別の量である。

保存np261020c_c26の4回置換/8位置receiptは一致。2回目52.5秒に双方でlive−cached=-7.33044236321706mを観測。元net、raw actorの遷移、nativeのwalkingarea形状作成式からI−J=-7.33044236321707mを独立再構成した。観測値を正解として埋め込まず、I/J/外部長/位置を一次形状から算出した。

再構成source/result：[数値証跡](audit_history/native_pair_c_numeric_reconstruction_20261020/result.json)。対象は同fixtureの直線lane・default detail=4・順方向内部遷移であり、一般網やnative継承guardを全件実証したものではない。

## 最小修正と検証

`walk_replacement_contract`内のlive長=固定計画長という誤った同一視を訂正した。live長は有限非負、旧route/中間receipt一致/現在位置/新長/時刻は従来どおり検査する。呼出側は別途、直前の固定計画長との一致、signed/model再帰、速度積分、残経路、新計画長・予算を照合する。実行器・PAP・3000m予算式・入力・native bundleは変更していない。

REDは人工live長上下2反例で旧照合が拒否することを確認。GREEN20試験は非有限/負値、live長へ予算を再anchorする改変、位置/route/時刻/新長、速度、Warningの不足/未知/余剰、版来歴、core境界を含む。旧c26 raw全7成分再計算はPASSだが、報告はINCOMPLETE/historicalで採用不可。元INVALID・失敗state・全case原本のSHA不変を確認した。

レビュー・旧版・差分・全ログ：[修正証跡](audit_history/native_live_length_validator_20261020/review.json)。変更したproduction関数はwalk_replacement_contractだけ。式・研究条件の変更ではない。live getter全値の一般的幾何再検証を保証せず、物理native guard/全suite/audit/14smoke/入力unit/preflight/G6は残る。
