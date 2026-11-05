"""Installation record: byte-preserving additions to canonical documents, once."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RECORD = []


def add(name, text, before=None, after=None):
    path = ROOT / name
    original = path.read_bytes()
    payload = text.replace('\n', '\r\n').encode('utf-8')
    if payload in original:
        raise RuntimeError('Already recorded: ' + name)
    if before is not None or after is not None:
        marker = (before if before is not None else after).encode('utf-8')
        matches = []
        offset = 0
        for line in original.splitlines(keepends=True):
            if line.strip() == marker:
                matches.append(offset if before is not None else offset + len(line))
            offset += len(line)
        if len(matches) != 1:
            raise RuntimeError('Ambiguous marker: ' + name)
        at = matches[0]
    else:
        at = len(original)
    result = original[:at] + payload + original[at:]
    assert result[:at] + result[at + len(payload):] == original
    if path.read_bytes() != original:
        raise RuntimeError('Concurrent edit: ' + name)
    path.write_bytes(result)
    assert path.read_bytes() == result and b'\x00' not in payload
    RECORD.append({'path': name, 'before_sha256': hashlib.sha256(original).hexdigest(),
                   'after_sha256': hashlib.sha256(result).hexdigest(),
                   'inserted_bytes': len(payload), 'outside_inserted_bytes_unchanged': True})


add('00_全体整理/現状把握_静的・動的シミュレーション整理.md', '''
- 独立監視を`07_監視システム/`へ導入。終了は1秒、状態・ログは10秒でローカル確認し、新規イベント時だけWindows通知と読取専用Codex診断を起動する。18試験と人工通知・診断probeが通過。監視自身の異常終了後、毎分救済トリガーによる別PIDでの自動復帰と履歴349件・重複イベント0を確認。旧RestartOnFailureの未復帰と失敗試行は保存。研究run・入力・PAP・受入変更なし。[導入記録](../05_タスク管理/jdrt/独立監視システム_導入タスク.md)。

''', after='### 2026-10-20')

add('context.md', '''
**独立監視導入（2026-10-20）：** ユーザー依頼の別goalとして`07_監視システム/`を導入。Windowsタスク`JDRT-SimulationWatch`でチャット外に常駐し、PID終了1秒・状態/ログ10秒・時刻停滞10分でイベント検出、イベント時だけ読取専用Codex短報とWindows通知。履歴349件を基準登録、研究core稼働0・READY=falseは専用statusで観測。人工通知/診断・18試験・監視異常終了からの別PID自動復帰を確認。runtimeはOneDrive外の`~/.jdrt-monitor/10afa40fb646/`、受信箱は同所`status.html`。このchatへの自動投稿・研究の自動start/recordは行わず、既存研究ゲートを維持。経過報告は現状把握Markdown先行→HTML反映。[導入タスク](05_タスク管理/jdrt/独立監視システム_導入タスク.md)。監視生存の最新状態は専用`watch.py status`を確認する。

''', before='<!-- AGENT_CURRENT_END -->')

add('00_全体整理/INDEX.md', '''
- [独立シミュレーション監視](../07_監視システム/README.md)・[導入タスク/検証記録](../05_タスク管理/jdrt/独立監視システム_導入タスク.md)：チャット外の終了/異常検出、イベント受信箱、Windows常駐・必要時だけの診断。研究開始ゲートは既存正本を維持。

''', before='## 1. トップレベル構成')

add('05_タスク管理/jdrt/JDRT_実装タスク管理.md', '''

## 2026-10-20 — 独立監視の導入

ユーザーの明示依頼により、定型の15分AI確認をイベント時だけの診断へ置き換える独立監視を導入した。[導入タスク](独立監視システム_導入タスク.md)を実装・検証記録の正本とする。18試験、人工通知/診断、監視自身の異常終了からの自動復帰を確認。旧監視は既にPAUSEDで、重複起動しない。監視の正常表示・完了イベントを研究validate PASS/採用と読み替えず、READY・1セル実行・独立検証・正式記録ゲートを維持する。研究実行器/入力・PAPの変更、研究run開始は本作業では行っていない。
''')

add('00_全体整理/決定ログ.md', '''

### 2026-10-20 — チャット外のイベント監視を導入

ユーザーの「このプログラムの導入を進めて」「進め方は、このプロジェクトの従来通り記録しながら行うこと。このシステム構築に独立フォルダを用意して良い」、続くgoal実行指定に基づき、`07_監視システム/`へ独立監視を構築した。平常時のLLM確認をやめ、通常プログラムのPID/進捗/ログ観測→イベント永続化→Windows通知・必要時だけの読取専用Codex診断とする。研究runの開始・強制終了・復旧・採用は自動診断へ許可しない。登録上存在したRestartOnFailureは実機で未復帰だったため、Microsoftの反復トリガー仕様を確認し、毎分の救済起動とIgnoreNew・OS lockへ変更。意図した監視プロセスだけの異常終了後に別PIDで自動復帰し、既存349件維持・イベント重複0を実測。18試験・人工通知/診断が通過。旧失敗試行・設定・観測は保全し、成功をnative回帰・研究READYへ転用しない。モデル起動要求は運用正本のgpt-6-luna/low、親chat設定は不変、内部backend独立確認はなし。詳細と証拠は[導入タスク](../05_タスク管理/jdrt/独立監視システム_導入タスク.md)。
''')

add('.agents/skills/joso-jdrt-runner/SKILL.md', '''

## Independent event monitoring (2026-10-20)

The user authorized a chat-independent Windows observer in `07_監視システム/`. Before creating another heartbeat, read its [operations](../../../../07_監視システム/README.md) and run its `watch.py status`; do not duplicate an existing monitor. It checks process exits every second and discovers state/progress/log changes every ten seconds without LLM calls. Events alone trigger notification and read-only Codex triage. This replaces routine fifteen-minute **AI** wakeups for configured targets, not the registered `check → validate → record → status` gates. No automatic research start, kill, recovery or adoption is exposed. Existing detailed helpers remain available for evidence audits. Read [routine operations](references/routine_operations.md) for the integration record and boundaries.
''')

add('.agents/skills/joso-jdrt-runner/references/routine_operations.md', '''

## Independent Windows event observer (2026-10-20)

For the authorized local choice/native targets, use the existing `07_監視システム/watch.py status` before scheduling more chat heartbeats. The Windows task `JDRT-SimulationWatch` owns the chat-independent observer. Its process rescue trigger runs each minute, with IgnoreNew and an OS lock; this is not a periodic AI invocation. Exit checks use process handles/creation identity every second; discovery/progress/incremental-log observation runs every ten seconds. Event JSON is durable before desktop notification and bounded, read-only Codex triage. The local inbox is `status.html` under the runtime printed by `status`. Previous terminal history is baselined once; later monitor restarts preserve deduplication and delivery states. A delivery interrupted by monitor death is retained for explicit inspection, not automatically replayed.

Read the [operations](../../../../../07_監視システム/README.md) for scope, stop/disable, model request, notification limitations and installation. The choice research CLI and all detailed audit helpers are unchanged. These lightweight observations do not establish formal SHA/accounting PASS, native physical regression, current READY, six-file recording or permission to start a subsequent core. Existing native owner/child independent audits remain distinct from the observer's owner-state monitoring. Do not rerun completed research series or interpret old FAILED manifests as new events.

Revision evidence: [installation task](../../../../../05_タスク管理/jdrt/独立監視システム_導入タスク.md), with pre-edit skill/reference bytes and SHA in `07_監視システム/verification/originals/`. Eighteen contract/integration tests, artificial notification/triage and actual scheduled recovery verify this operational integration. Research implementations, inputs and acceptance remain unchanged by this installation.
''')

add('05_タスク管理/スキル・エージェント運用.md', '''

## 2026-10-20 — 独立監視の運用追加

ユーザー明示の構築依頼とgoalにより[独立監視](../07_監視システム/README.md)を導入。`joso-jdrt-runner`の反復監視入口から利用し、設定対象の平常監視ではLLMを起動しない。WindowsタスクとOS lockで監視writerを一つに保ち、イベント時だけ`gpt-6-luna / low`指定の読取専用CLI短報を起動する。これは親chatのモデル切替や一般的なサブエージェント委任許可を追加するものではない。CLIの指定・応答と実backendの独立証明を区別する。

診断にはツール使用・別agent起動・外部メッセージ送信・研究start/kill/recover/validate/recordを許可しない。失敗・中断・異常は保全し、既存の担当chatが従来ゲートに従って対応する。新たな15分heartbeatを作る前に独立監視statusと既存自動化の稼働を照合する。詳細試験・旧版SHA・導入時の失敗と修正は[導入タスク](jdrt/独立監視システム_導入タスク.md)と検証資料に保持する。
''')

(HERE / 'document_edits.json').write_text(json.dumps(RECORD, ensure_ascii=False, indent=2), encoding='utf-8')
print('Recorded', len(RECORD), 'byte-preserving canonical additions; Markdown precedes derived HTML.')
