# 受付・代替行動 停車履歴v5：正式実験記録

登録：choice_shared_stopindex_v5_20261029

正式0/70。技術準備中・READY=false。旧系列・smoke・fixtureを採用しない。正式採用は専用CLI recordのみ。


<!-- choice_record:sv26103001 -->
### sv26103001（2026-10-30T10:24:12.352232+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_shared_stopindex_v5_20261029、cell=fixed_reference_r0_seed23423、R0、seed=23423。独立検証PASS・研究採用可。人物11965、要求0。主指標の施設受入=0/544、退出182は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5/validation_reports/validate_sv26103001_20261030T102412267412.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:sv26103002 -->
### sv26103002（2026-10-30T19:31:57.986923+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_shared_stopindex_v5_20261029、cell=fixed_reference_u05_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5/validation_reports/validate_sv26103002_20261030T193157904132.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:sv26103003 -->
### sv26103003（2026-10-30T21:12:27.830821+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_shared_stopindex_v5_20261029、cell=fixed_reference_u05_r2p900_seed23423、R2P900、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5/validation_reports/validate_sv26103003_20261030T211227634395.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:sv26103004 -->
### sv26103004（2026-10-30T22:08:46.487181+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_shared_stopindex_v5_20261029、cell=fixed_reference_u05_r2p0_seed23423、R2P0、seed=23423。独立検証PASS・研究採用可。人物11965、要求90。主指標の施設受入=0/544、退出183は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5/validation_reports/validate_sv26103004_20261030T220846395559.json`。次の1件は専用CLI statusを参照。


<!-- choice_record:sv26103005 -->
### sv26103005（2026-10-30T23:03:38.842888+09:00正式記録）

protocol=realtime_choice_v1、registration=choice_shared_stopindex_v5_20261029、cell=fixed_reference_u50_r1_seed23423、R1、seed=23423。独立検証PASS・研究採用可。人物11965、要求900。主指標の施設受入=1/544、退出181は別計上。全登録セル完了前に方向解釈しない。
一次検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5/validation_reports/validate_sv26103005_20261030T230338736682.json`。次の1件は専用CLI statusを参照。

### sv26103006（2026-11-06 INVALID保全・不採用）

cell=fixed_reference_u50_r2p900_seed23423。10/30に旧OneDrive rootで完走した後、11/6にローカルrootで独立validateを行いINVALIDとなった。不一致は実行環境の絶対パス3件だけで、SHAはすべて一致。専用rejectでINVALID_PRESERVEDとした。正式記録ではなく、台帳行もない。同じセルは学校PCで新しいREADYを取った後、新しいrun IDで実行する。経緯は決定ログ2026-11-06。
検証：`04_プログラム/output/sumo/regions/08211/experiments/jdrt_realtime_choice_stopindex_v5/validation_reports/validate_sv26103006_20261106T180735332274.json`／診断：`…/driver_logs/sv26103006.diagnosis.json`。
