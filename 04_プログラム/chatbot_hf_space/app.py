import glob
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock

import faiss
import gradio as gr
from sentence_transformers import SentenceTransformer


REPO_URL = os.getenv(
    "REPO_URL",
    "https://github.com/23f302020/joso-evacuation-simulation",
)
REPO_DIR = Path(os.getenv("REPO_DIR", "/tmp/joso-evacuation-simulation"))
DOC_GLOB = os.getenv("DOC_GLOB", "**/*.md")
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b:fastest")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")
LLM_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "LLM_FALLBACK_MODELS",
        "Qwen/Qwen3-4B-Thinking-2507:fastest,deepseek-ai/DeepSeek-V4-Pro:fastest",
    ).split(",")
    if model.strip()
]
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "https://router.huggingface.co/v1/chat/completions")
HF_TOKEN = os.getenv("HF_TOKEN")
TOP_K = int(os.getenv("TOP_K", "4"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
DOCUMENTS = None
CHUNKS = None
EMBEDDER = None
VECTOR_INDEX = None
INDEX_LOCK = Lock()
KEY_TERMS = [
    "Phase 1",
    "Phase 2",
    "Phase 3",
    "phase1",
    "phase2",
    "phase3",
    "SUMO",
    "TraCI",
    "未到着",
    "到着",
    "逃げ遅れ",
    "出発",
    "閉鎖",
    "浸水",
    "避難所",
    "避難開始",
    "避難",
    "自家用車",
    "バス",
    "デマンド交通",
    "経路",
    "時間軸",
    "常総市",
    "small",
    "10pct",
    "full",
]


def clone_repository() -> None:
    if REPO_DIR.exists():
        return
    subprocess.run(
        ["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)],
        check=True,
        text=True,
    )


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def should_skip(path: Path) -> bool:
    ignored_parts = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "cache",
    }
    return any(part in ignored_parts for part in path.parts)


def load_documents() -> list[dict]:
    clone_repository()
    documents = []
    for raw_path in glob.glob(str(REPO_DIR / DOC_GLOB), recursive=True):
        path = Path(raw_path)
        if should_skip(path):
            continue
        text = read_text(path).strip()
        if not text:
            continue
        rel_path = path.relative_to(REPO_DIR).as_posix()
        documents.append({"source": rel_path, "text": text})
    return documents


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = "\n".join(line.rstrip() for line in text.splitlines())
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n##", start, end), text.rfind("\n\n", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def build_chunks(documents: list[dict]) -> list[dict]:
    chunks = []
    for doc in documents:
        for index, chunk in enumerate(split_text(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP), start=1):
            chunks.append(
                {
                    "source": doc["source"],
                    "chunk_id": index,
                    "text": chunk,
                }
            )
    return chunks


def e5_passages(texts: list[str]) -> list[str]:
    return [f"passage: {text}" for text in texts]


def e5_query(text: str) -> str:
    return f"query: {text}"


def build_vector_index(chunks: list[dict]):
    model = SentenceTransformer(EMBED_MODEL)
    embeddings = model.encode(
        e5_passages([chunk["text"] for chunk in chunks]),
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype("float32")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return model, index


def ensure_index_ready() -> None:
    global DOCUMENTS, CHUNKS, EMBEDDER, VECTOR_INDEX
    if VECTOR_INDEX is not None:
        return
    with INDEX_LOCK:
        if VECTOR_INDEX is not None:
            return
        print("Loading documents and building vector index...")
        DOCUMENTS = load_documents()
        CHUNKS = build_chunks(DOCUMENTS)
        if not CHUNKS:
            raise RuntimeError("No documents were loaded from the repository.")
        EMBEDDER, VECTOR_INDEX = build_vector_index(CHUNKS)
        print(f"Ready: {len(DOCUMENTS)} files, {len(CHUNKS)} chunks")


def retrieve(question: str) -> list[dict]:
    ensure_index_ready()
    query_embedding = EMBEDDER.encode(
        [e5_query(question)],
        normalize_embeddings=True,
    ).astype("float32")
    scores, ids = VECTOR_INDEX.search(query_embedding, TOP_K)
    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        item = dict(CHUNKS[int(idx)])
        item["score"] = float(score)
        results.append(item)
    return results


def build_messages(question: str, contexts: list[dict]) -> list[dict]:
    context_text = "\n\n---\n\n".join(
        f"[source: {item['source']}#{item['chunk_id']}]\n{item['text']}" for item in contexts
    )
    return [
        {
            "role": "system",
            "content": (
                "あなたは鬼怒川氾濫避難シミュレーション研究のQ&Aアシスタントです。"
                "必ず与えられたコンテキストに基づいて日本語で簡潔に回答してください。"
                "思考過程、検討メモ、英語の前置き、引用文の長い転記は出力しないでください。"
                "最終回答だけを2〜4文で出力してください。"
                "コンテキストにない情報は推測せず、「資料に記載がありません」と答えてください。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"コンテキスト:\n{context_text}\n\n"
                f"質問:\n{question}\n\n"
                "出力条件:\n"
                "- 日本語のみ\n"
                "- 最終回答のみ\n"
                "- 2〜4文\n"
                "- 「考えます」「まず」「according to」「let me」などの思考過程は禁止\n"
            ),
        },
    ]


def llm_model_id() -> str:
    if ":" in LLM_MODEL or not LLM_PROVIDER:
        return LLM_MODEL
    return f"{LLM_MODEL}:{LLM_PROVIDER}"


def post_chat_completion(model_id: str, messages: list[dict]) -> str:
    payload = json.dumps(
        {
            "model": model_id,
            "messages": messages,
            "max_tokens": 180,
            "temperature": 0.2,
            "stop": ["\n\n参照ファイル:", "参照ファイル:"],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        LLM_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{model_id}: HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"{model_id}: {type(exc).__name__}: {exc}") from exc


def call_llm(messages: list[dict]) -> str:
    if not HF_TOKEN:
        return "回答生成中にエラーが発生しました。\n\n- HF_TOKEN is not set."
    candidates = []
    for model_id in [llm_model_id(), *LLM_FALLBACK_MODELS]:
        if model_id not in candidates:
            candidates.append(model_id)
    errors = []
    for model_id in candidates:
        try:
            return post_chat_completion(model_id, messages)
        except Exception as exc:
            errors.append(str(exc))
            print(f"LLM candidate failed: {exc}")
    detail = "\n".join(f"- {error[:600]}" for error in errors[:3])
    return f"回答生成中にエラーが発生しました。\n\n{detail}"


def cleanup_llm_answer(answer: str, question: str, contexts: list[dict]) -> str:
    answer = (answer or "").strip()
    if not answer:
        return format_minimal_answer(question, contexts)
    banned_markers = [
        "Okay,",
        "Okay, let me",
        "Let me",
        "First,",
        "First, I'll",
        "First, I need",
        "I need to",
        "The user's question",
        "According to the context",
        "So the answer should be",
    ]
    if any(marker.lower() in answer.lower() for marker in banned_markers):
        return format_minimal_answer(question, contexts)
    japanese_chars = len(re.findall(r"[一-龥ぁ-んァ-ヶー]", answer))
    latin_words = len(re.findall(r"[A-Za-z]{3,}", answer))
    head = answer[:240]
    head_latin_words = len(re.findall(r"[A-Za-z]{3,}", head))
    head_japanese_chars = len(re.findall(r"[一-龥ぁ-んァ-ヶー]", head))
    if japanese_chars < 20 or latin_words > japanese_chars or head_latin_words > head_japanese_chars:
        return format_minimal_answer(question, contexts)
    answer = re.sub(r"(?is)<think>.*?</think>", "", answer).strip()
    answer = re.sub(r"(?i)^(final answer|answer)\\s*[:：]\\s*", "", answer).strip()
    return answer


def extract_question_terms(question: str) -> list[str]:
    terms = []
    lowered = question.lower()
    for term in KEY_TERMS:
        if term.lower() in lowered:
            terms.append(term)
    for token in re.findall(r"[A-Za-z0-9_]+|[一-龥ぁ-んァ-ヶー]{2,}", question):
        if token not in terms and token not in {"ですか", "ますか", "について", "どういう", "どのよう"}:
            terms.append(token)
    return terms


def split_candidate_sentences(text: str) -> list[str]:
    sentences = []
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("|").strip()
        if not line or re.fullmatch(r"[-:|\s]+", line):
            continue
        if line.startswith("```"):
            continue
        if "|" in line:
            cleaned = " / ".join(part.strip() for part in line.split("|") if part.strip())
            if cleaned:
                sentences.append(cleaned)
            continue
        for part in re.split(r"(?<=[。．.!?？])\s+|。", line):
            cleaned = part.strip(" -・\t")
            if len(cleaned) >= 18:
                sentences.append(cleaned + ("。" if not cleaned.endswith(("。", "．", ".", "!", "?", "？")) else ""))
    return sentences


def select_answer_sentences(question: str, contexts: list[dict], limit: int = 3) -> list[str]:
    terms = extract_question_terms(question)
    question_chars = {char for char in question if re.match(r"[A-Za-z0-9一-龥ぁ-んァ-ヶー]", char)}
    question_has_unarrived_count = "未到着" in question and re.search(r"14\\s*台|14", question)
    scored = []
    seen = set()
    for item in contexts:
        for sentence in split_candidate_sentences(item["text"]):
            normalized = " ".join(sentence.split())
            if normalized in seen:
                continue
            seen.add(normalized)
            lowered = normalized.lower()
            score = 0
            for term in terms:
                if term.lower() in lowered:
                    score += max(3, min(len(term), 12))
            if question_has_unarrived_count and "14" in normalized and "未到着" in normalized:
                if any(keyword in normalized for keyword in ("閉鎖", "出発", "発車", "逃げ遅れ", "未完走")):
                    score += 45
                if "渋滞" in normalized and ("ではなく" in normalized or "なく" in normalized):
                    score += 15
                if "直接比較" in normalized:
                    score -= 35
            sentence_chars = {char for char in normalized if re.match(r"[A-Za-z0-9一-龥ぁ-んァ-ヶー]", char)}
            score += len(question_chars & sentence_chars) * 0.2
            if score > 0:
                scored.append((score, len(normalized), normalized))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [sentence for _, _, sentence in scored[:limit]]


def format_minimal_answer(question: str, contexts: list[dict], reason: str | None = None) -> str:
    selected = select_answer_sentences(question, contexts)
    if selected:
        answer_body = " ".join(selected)
        if len(answer_body) > 900:
            answer_body = answer_body[:900].rstrip() + "..."
        prefix = "資料に基づく回答です。"
        if reason:
            prefix += f"\n{reason}"
        return f"{prefix}\n\n{answer_body}"
    return (
        "資料に基づく回答です。\n"
        f"{reason + chr(10) if reason else ''}"
        "関連資料は取得できましたが，質問に直接対応する記述は特定できませんでした。"
        "参照ファイルを確認してください。"
    )


def answer_question(question: str) -> str:
    contexts = retrieve(question)
    if not HF_TOKEN:
        answer = format_minimal_answer(
            question,
            contexts,
            "HF_TOKEN未設定のため，検索資料から短い回答文を作成しています。",
        )
    else:
        messages = build_messages(question, contexts)
        answer = cleanup_llm_answer(call_llm(messages), question, contexts)
        if answer.startswith("回答生成中にエラーが発生しました。"):
            answer = format_minimal_answer(
                question,
                contexts,
                "LLM推論に失敗したため，検索資料から短い回答文を作成しています。",
            )
    sources = []
    for item in contexts:
        label = f"{item['source']}#{item['chunk_id']}"
        if label not in sources:
            sources.append(label)
    source_text = "\n".join(f"- {source}" for source in sources[:TOP_K])
    return f"{answer}\n\n参照ファイル:\n{source_text}"


def respond(message, history):
    message = (message or "").strip()
    if not message:
        return "", history
    history = history or []
    history.append({"role": "user", "content": [{"type": "text", "text": message}]})
    try:
        answer = answer_question(message)
    except Exception as exc:
        answer = f"エラーが発生しました: {type(exc).__name__}: {exc}"
    history.append({"role": "assistant", "content": [{"type": "text", "text": answer}]})
    return "", history


with gr.Blocks(title="避難シミュレーション研究 Q&A") as demo:
    gr.Markdown(
        "## 避難シミュレーション研究 Q&A\n"
        "GitHubリポジトリ内のMarkdown資料を検索し、参照ファイル付きで回答します。"
        "初回質問時は資料読み込みと検索インデックス構築のため、少し時間がかかります。"
    )
    chatbot = gr.Chatbot(height=460)
    question = gr.Textbox(
        placeholder="例：Phase 2の未到着14台は何を意味しますか？",
        label="質問",
    )
    with gr.Row():
        send_button = gr.Button("送信", variant="primary")
        clear_button = gr.ClearButton([question, chatbot], value="履歴を消去")

    send_button.click(respond, [question, chatbot], [question, chatbot])
    question.submit(respond, [question, chatbot], [question, chatbot])


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        ssr_mode=False,
    )
