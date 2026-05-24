import glob
import os
import shutil
import subprocess
from pathlib import Path

import faiss
import gradio as gr
import numpy as np
from huggingface_hub import InferenceClient
from sentence_transformers import SentenceTransformer


REPO_URL = os.getenv(
    "REPO_URL",
    "https://github.com/23f302020/joso-evacuation-simulation",
)
REPO_DIR = Path(os.getenv("REPO_DIR", "/tmp/joso-evacuation-simulation"))
DOC_GLOB = os.getenv("DOC_GLOB", "**/*.md")
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
TOP_K = int(os.getenv("TOP_K", "4"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))


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


print("Loading documents and building vector index...")
DOCUMENTS = load_documents()
CHUNKS = build_chunks(DOCUMENTS)
if not CHUNKS:
    raise RuntimeError("No documents were loaded from the repository.")
EMBEDDER, VECTOR_INDEX = build_vector_index(CHUNKS)
LLM_CLIENT = InferenceClient(token=HF_TOKEN)
print(f"Ready: {len(DOCUMENTS)} files, {len(CHUNKS)} chunks")


def retrieve(question: str) -> list[dict]:
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
                "コンテキストにない情報は推測せず、「資料に記載がありません」と答えてください。"
            ),
        },
        {
            "role": "user",
            "content": f"コンテキスト:\n{context_text}\n\n質問:\n{question}",
        },
    ]


def call_llm(messages: list[dict]) -> str:
    try:
        response = LLM_CLIENT.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=512,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        fallback_prompt = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        try:
            response = LLM_CLIENT.text_generation(
                fallback_prompt,
                model=LLM_MODEL,
                max_new_tokens=512,
                temperature=0.2,
                return_full_text=False,
            )
            return str(response).strip()
        except Exception as fallback_exc:
            return (
                "回答生成中にエラーが発生しました。"
                f"\n\n- chat completion: {exc}"
                f"\n- text generation: {fallback_exc}"
            )


def answer_question(question: str) -> str:
    contexts = retrieve(question)
    messages = build_messages(question, contexts)
    answer = call_llm(messages)
    sources = []
    for item in contexts:
        label = f"{item['source']}#{item['chunk_id']}"
        if label not in sources:
            sources.append(label)
    source_text = "\n".join(f"- {source}" for source in sources[:TOP_K])
    return f"{answer}\n\n参照ファイル:\n{source_text}"


def respond(message: str, history: list[dict]):
    message = (message or "").strip()
    if not message:
        return "", history
    history = history or []
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer_question(message)})
    return "", history


with gr.Blocks(title="避難シミュレーション研究 Q&A") as demo:
    gr.Markdown(
        "## 避難シミュレーション研究 Q&A\n"
        "GitHubリポジトリ内のMarkdown資料を検索し、参照ファイル付きで回答します。"
    )
    chatbot = gr.Chatbot(type="messages", height=460)
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
    demo.launch()
