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
| UI | Gradio | Space上のチャットUI |
| LLM推論 | Hugging Face Inference Providers | `HF_TOKEN` をSpace Secretsに登録 |
| 既定LLM | `Qwen/Qwen2.5-1.5B-Instruct` | 日本語応答を考慮した軽量な多言語モデルとして採用 |
| 代替LLM候補 | `HuggingFaceH4/zephyr-7b-beta` | `ChatBot.md` に記載されていた候補 |
| 埋め込みモデル | `intfloat/multilingual-e5-small` | 日本語資料検索を考慮して採用 |
| ベクトル検索 | FAISS | Space起動時にインメモリで構築 |
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
7. `Qwen/Qwen2.5-1.5B-Instruct` により日本語回答を生成する．
8. 回答末尾に参照ファイルを表示する．

## 制約

- 無料のCPU Basic Spaceは一定時間アクセスがないとスリープするため，初回表示に時間がかかる場合がある．
- Inference Providersは無料クレジット内での利用を想定する．利用量が増える場合は料金設定の確認が必要である．
- Spaceのファイルシステムは永続化されないため，起動ごとにcloneとベクトルインデックス構築を行う．
- 回答はMarkdown資料に基づくため，CSVやPythonコードの詳細を回答対象に含めたい場合は読み込み対象を拡張する必要がある．

## 参照URL

- Hugging Face Spaces概要：https://huggingface.co/docs/hub/spaces-overview
- Hugging Face SpacesのHTML埋め込み：https://huggingface.co/docs/hub/en/spaces-embed
- Hugging Face Inference Providers料金：https://huggingface.co/docs/inference-providers/pricing
- Gradio公式ドキュメント：https://www.gradio.app/docs
- Sentence Transformers公式ドキュメント：https://www.sbert.net/
- FAISS公式リポジトリ：https://github.com/facebookresearch/faiss
