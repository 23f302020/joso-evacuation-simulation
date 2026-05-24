---
title: Joso Evacuation Research Chatbot
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# Joso Evacuation Research Chatbot

GitHubリポジトリ内のMarkdown資料を知識源として検索し，日本語で回答するRAGチャットボットである．

## 使用する主なシステム

| 役割 | 名称 |
|---|---|
| ホスティング | Hugging Face Spaces |
| UI | Gradio |
| LLM推論 | Hugging Face Inference Providers |
| 既定LLM | `Qwen/Qwen2.5-1.5B-Instruct` |
| 埋め込みモデル | `intfloat/multilingual-e5-small` |
| ベクトル検索 | FAISS |
| 知識源 | `https://github.com/23f302020/joso-evacuation-simulation` のMarkdownファイル |

## 環境変数

| 変数 | 用途 | 既定値 |
|---|---|---|
| `HF_TOKEN` | Hugging Face Inference Providersの認証 | SpaceのSecretsで設定 |
| `REPO_URL` | 読み込むGitHubリポジトリ | `https://github.com/23f302020/joso-evacuation-simulation` |
| `DOC_GLOB` | 読み込むファイル | `**/*.md` |
| `LLM_MODEL` | 回答生成モデル | `Qwen/Qwen2.5-1.5B-Instruct` |
| `EMBED_MODEL` | 埋め込みモデル | `intfloat/multilingual-e5-small` |

## デプロイ手順

1. Hugging Faceで `joso-evacuation-chatbot` というGradio Spaceを作成する．
2. SpaceのSettingsでSecret `HF_TOKEN` を登録する．
3. 本フォルダ内の `app.py`，`requirements.txt`，`README.md` をSpaceへ配置する．
4. Spaceの起動後，`https://<ユーザー名>-joso-evacuation-chatbot.hf.space` を `faq.html` の埋め込みURLとして使用する．

## 注意

無料のCPU Basic Spaceは，一定時間アクセスがないとスリープする．発表や確認の前には，一度Spaceを開いて起動状態にしておく．
