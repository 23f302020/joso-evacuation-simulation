# Native選定比較fの確認と内部trace準備

2026-10-21。正式0/70、研究core稼働0、READY=false。選定比較の完了だけで研究結果やnative全回帰の完了とはしない。

## 選定比較f

`nc261020f_native_pair/state.json`はSELECTED_PAIR_VERIFIED_PENDING_NATIVE_GUARDS。元の実行handleは終了コード0。全13,682 source/artifact bindingを現在のbytesから再SHA計算して不一致0。対照校正・修正版校正/反復の独立3報告は保存原本とstdoutが一致し、各7成分PASSを確認した。対照反復は予定したold_remainingのXYだけの不連続。修正版反復は4回reroute・8receiptを元eventから再計算し、位置差なし。2caseの物理入力/canonical netは一致、各toolchain receiptはそのroleの固定bundleと完全照合済み。既存runや旧INVALID/失敗は変更していない。

根拠：[完了再照合](audit_history/native_pair_f_completion_20261021/result.json)・全binding監査JSON。これは技術的な位置置換の確認であり、70セルの方式間差を示さない。

## 内部traceの準備

新helperは、元native CPPへ5つの観測blockだけを挿入する。source除去後の完全一致、generator出力の完全一致、LF/CRLF、重複/欠損/改変拒否、既存RNG呼出し・copy/方向の保持を6試験で確認した。元Release/gnu++17の定義/includesを使う実g++の-fsyntax-onlyが終了コード0。元native sourceは不変、診断binaryはまだ作成していない。

根拠：[準備レビュー](audit_history/native_trace_source_20261021/review.json)・observation_only.patch・syntax_result.json。compileされた新binaryの実行やguard成立を意味しない。次は別source/build/outputとversion/SHAを持つ隔離診断build、その後に13群の実native traceと独立消費器、最終production binaryの広い回帰へ進む。全suite/audit/14smoke/input-unit/preflight/G6は残る。

## 観測の空白

朝の最初のstatusは昨夜23:52の観測を返したが、同じPID30168が復帰後に新しい観測を保存した。Windows Power-TroubleshooterのSleepTime/WakeTime、Kernel-Powerのstandby時刻を読取確認。期間中を監視済みと補作しない。旧PermissionErrorと別PIDへの継続は保全し、原因ファイルや起動主体を推測で確定しない。新しい監視や再起動は行わず、同source/同一性/40秒未満の鮮度を確認した。

根拠：07_監視システム/verification/resume_observation_20261021/result.jsonとpower_timing.json。個別fixtureの完了eventとflags空を確認したが、完了eventを正式検証PASSへ読み替えない。
