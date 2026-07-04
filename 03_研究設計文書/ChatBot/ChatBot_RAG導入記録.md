# ChatBot RAG導入記録

作成日：2026年5月22日

## 目的

`faq.html` のチャットボット用セクターに，GitHubリポジトリ内の研究資料を知識源とするRAGチャットボットを導入する．既存のFAQキーワードチャットは，Hugging Face Spaceの未起動時やネットワーク不通時の予備として残す．

## 採用方針

推奨方針として，Hugging Face Spaces上にGradioアプリを作成し，`faq.html` にはそのSpaceを `iframe` で埋め込む構成を採用する．

採用理由は以下の通りである．

- 既存のHTML成果物を大きく変更せず，`faq.html` のチャットボット用セクターに追加できる．
- Hugging Face SpacesはGradioアプリの公開とHTML埋め込みに対応している．
- RAG本体を外部Spaceに分離することで，GitHub PagesやローカルHTMLからも同じチャットボットを参照できる．
- 既存のFAQキーワードチャットを残すことで，Spaceのスリープや起動失敗時にも最低限の質疑応答が可能になる．

## 使用するシステム・AI

| 役割 | 採用名 | 備考 |
|---|---|---|
| ホスティング | Hugging Face Spaces | CPU Basicを想定 |
| UI | Gradio 6.5.1 | Space上のチャットUI．Python 3.13環境での互換性を考慮して6系を採用 |
| LLM推論 | Hugging Face Inference Providers | `HF_TOKEN` をSpace Secretsに登録 |
| 既定LLM | `openai/gpt-oss-120b:fastest` | Hugging Face公式例に近いProvider自動選択モデルとして採用 |
| 既定Provider | `:fastest` | Hugging Face RouterのChat Completions APIで利用可能なProviderを自動選択する |
| フォールバックLLM | `Qwen/Qwen3-4B-Thinking-2507:fastest`, `deepseek-ai/DeepSeek-V4-Pro:fastest` | 既定モデルが失敗した場合に順に試す |
| 代替LLM候補 | `HuggingFaceH4/zephyr-7b-beta` | `ChatBot.md` に記載されていた候補 |
| 埋め込みモデル | `intfloat/multilingual-e5-small` | 日本語資料検索を考慮して採用 |
| ベクトル検索 | FAISS | Space起動時にインメモリで構築 |
| 簡易回答生成 | 検索資料からの関連文抽出 | `HF_TOKEN` 未設定時も最低限の文章回答を返す |
| 知識源 | GitHubリポジトリのMarkdownファイル | `https://github.com/23f302020/joso-evacuation-simulation` |

## 実装ファイル

| ファイル | 役割 |
|---|---|
| `04_プログラム/chatbot_hf_space/app.py` | Gradio + RAGチャットボット本体 |
| `04_プログラム/chatbot_hf_space/requirements.txt` | Hugging Face Space用依存関係 |
| `04_プログラム/chatbot_hf_space/README.md` | Space設定とデプロイ手順 |
| `04_プログラム/output/faq.html` | RAGチャット埋め込み枠とFAQチャット予備枠 |

## faq.htmlへの導入内容

`faq.html#chatbot-section` に，Hugging Face Spaceを表示するRAGチャット枠を追加する．想定URLは以下である．

```text
https://23f302020-joso-evacuation-chatbot.hf.space
```

Hugging Faceのユーザー名やSpace名が異なる場合は，`faq.html` 内の `iframe` の `src` を実際のSpace URLに変更する．既存のFAQキーワードチャットは `faq-fallback-chatbot` として残し，RAGチャットが使用できない場合の代替手段とする．

## 実装方法

1. Space起動時にGitHubリポジトリを `/tmp` にcloneする．
2. リポジトリ内のMarkdownファイルを読み込む．
3. Markdown本文をチャンク分割する．
4. `intfloat/multilingual-e5-small` で各チャンクをベクトル化する．
5. FAISSで類似チャンク検索を行う．
6. 検索したチャンクとユーザー質問をプロンプトに含める．
7. Hugging Face RouterのChat Completions APIにより日本語回答を生成する．既定モデルは `openai/gpt-oss-120b:fastest` とし，失敗時はフォールバックモデルまたは検索資料からの短文回答に切り替える．
8. 回答末尾に参照ファイルを表示する．

## 制約

- 無料のCPU Basic Spaceは一定時間アクセスがないとスリープするため，初回表示に時間がかかる場合がある．
- Inference Providersは無料クレジット内での利用を想定する．利用量が増える場合は料金設定の確認が必要である．
- Spaceのファイルシステムは永続化されないため，起動ごとにcloneとベクトルインデックス構築を行う．
- 回答はMarkdown資料に基づくため，CSVやPythonコードの詳細を回答対象に含めたい場合は読み込み対象を拡張する必要がある．

## 発表時の推奨運用

Hugging Face Spacesの無料CPU Basicは，2 vCPU / 16GB RAMの無料実行環境であり，一定時間未使用の場合はスリープする．また，LLM回答に使うHugging Face Inference Providersは無料ユーザーにも月間クレジットがあるが，無料枠は小さく，利用量が増えると追加クレジット購入や制限の対象になり得る．

研究発表時は，以下の運用を推奨する．

1. 発表の10〜15分前に `https://23f302020-joso-evacuation-chatbot.hf.space` を開き，Spaceを起動しておく．
2. 発表前に代表質問を1回送信し，GitHub資料読込とベクトルインデックス構築を済ませておく．
3. 発表中は発表者PCでデモを行い，聴衆全員に同時アクセスさせる運用は避ける．
4. URLを共有する場合は，発表後の個別確認用とし，同時に多数が質問すると応答遅延・タイムアウト・無料クレジット消費が起きる可能性を説明する．
5. 回答生成に失敗した場合に備え，`faq.html` 内のFAQ予備チャットと，代表質問への回答スクリーンショットを準備しておく．
6. 発表直前の最終確認では，「Phase 2の未到着14台は何を意味しますか？」を送信し，日本語回答と参照ファイルが返ることを確認する．

発表時の説明としては，「このチャットボットはHugging Faceの無料Space上で動作しているため，多人数同時利用では応答が遅くなる可能性がある．発表では発表者PCで代表質問を実演し，必要に応じて後からURLを共有する」と述べる．

## 実装時の修正履歴

- `README.md` の `colorTo: cyan` はHugging Face Spaceで許可されていないため，`colorTo: indigo` に変更した．
- Python 3.13環境でGradio依存の `audioop` が不足したため，`requirements.txt` に `audioop-lts>=0.2.2` を追加した．
- Gradio 4.44では `huggingface_hub` 1.xとの互換性や起動設定で問題が出たため，Space SDKと依存関係をGradio 6.5.1へ更新した．
- 起動時にGitHub資料読み込みとFAISS構築を行うとSpaceの起動が重くなるため，初回質問時にインデックスを構築する遅延実行方式へ変更した．
- `HF_TOKEN` 未設定時やLLM推論失敗時でも，関連資料検索結果と本文抜粋を返すフォールバックを追加した．
- その後，発表確認時に通常の回答文として読めるように，`HF_TOKEN` 未設定時も検索資料から関連文を選び，最低限の短い文章回答を返す方式へ変更した．
- `HF_TOKEN` 設定後の公開Space確認で，モデルをProviderなしで呼ぶと `model_not_supported` となったため，Hugging Face RouterのChat Completions APIへ直接POSTする方式へ変更した．
- その後，`Qwen/Qwen2.5-1.5B-Instruct:featherless-ai` でもLLM生成が成立しなかったため，既定モデルをProvider自動選択の `openai/gpt-oss-120b:fastest` に変更し，複数モデルを順に試す方式へ変更した．
- `openai/gpt-oss-120b:fastest` ではLLM呼び出し自体は成立したが，英語の思考過程が回答に含まれたため，system promptを強化し，不適切な回答形式を検出した場合は日本語の短文回答へ切り替える後処理を追加した．

## 動作確認状況

2026年5月25日に，公開Space `https://23f302020-joso-evacuation-chatbot.hf.space` のトップ画面と `/config` がHTTP 200を返すことを確認した．また，Gradio API `respond` に「Phase 2の未到着14台は何を意味しますか？」を送信し，`event: complete` で応答が返ることを確認した．

2026年5月25日の追加修正で，`HF_TOKEN` が未設定でも検索資料から短い回答文を作成するように変更した．LLMによる自然な文章生成を有効化する場合は，Hugging Face SpaceのSettingsで `HF_TOKEN` をSecretとして登録する．

同日，`HF_TOKEN` 設定後の公開Space確認ではSecret自体は読み込まれたが，既定モデル・Provider指定の組み合わせでLLM生成が失敗した．このため，`app.py` をHugging Face Routerの `:fastest` 方式と複数モデルフォールバックで呼び出す方式に修正した．

同日，`openai/gpt-oss-120b:fastest` 反映後にLLM生成は成立したが，出力に英語の思考過程が混入した．研究発表・確認用チャットでは最終回答だけを表示する必要があるため，回答整形と日本語短文へのフォールバックを追加した．

公開Space確認では，`Okay, let's...` から始まる英語の思考過程がまだ残ったため，回答冒頭の英語検出条件を強化した．英語の思考過程を検出した場合は，LLM出力をそのまま表示せず，検索資料から作成する日本語短文回答へ切り替える．

英語思考過程除去後の公開Space確認では，技術的な応答は成立したが，「未到着14台」の直接理由よりもPhase 1/Phase 2の指標差分説明が優先された．このため，`未到着14台` に関する質問では，`閉鎖`，`出発`，`発車`，`逃げ遅れ`，`未完走` を含む文を優先し，`直接比較しない` を含む文の優先度を下げるよう回答選択ロジックを調整した．

最新版の公開Space確認では，`Phase 2の未到着14台は何を意味しますか？` に対して，閉鎖済みの出発edgeから発車できなかった車両であり，混雑による未到着とは分けて扱うという回答が返った．`HF_TOKEN` 未設定表示，LLM失敗表示，英語思考過程は出ておらず，参照ファイルも表示されたため，RAGチャットボットは研究説明用として利用可能な状態になった．

## 参照URL

- Hugging Face Spaces概要：https://huggingface.co/docs/hub/spaces-overview
- Hugging Face SpacesのHTML埋め込み：https://huggingface.co/docs/hub/en/spaces-embed
- Hugging Face Inference Providers料金：https://huggingface.co/docs/inference-providers/pricing
- Gradio公式ドキュメント：https://www.gradio.app/docs
- Sentence Transformers公式ドキュメント：https://www.sbert.net/
- FAISS公式リポジトリ：https://github.com/facebookresearch/faiss
