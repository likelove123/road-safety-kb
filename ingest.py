"""把 data/raw 下的文档解析、按“第X条”切分，产出 data/chunks.jsonl；
填了 API_KEY 时顺带写入向量库。

用法：
    .venv\\Scripts\\python.exe ingest.py            解析 + 切分 + 建索引
    .venv\\Scripts\\python.exe ingest.py --no-index 只切分，不建索引（不需要 Key）
"""
import argparse
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import config

# 条款起始标记：行首的“第X条”
ART_LINE = re.compile(r"(?m)^\s*(第[一二三四五六七八九十百千零〇两0-9]+条)\s*")
# 兜底：PDF 提取后可能没有换行
ART_INLINE = re.compile(r"(第[一二三四五六七八九十百千零〇两0-9]+条)[\s　]+")
SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        import docx
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8", errors="ignore")


def split_by_article(text: str) -> list[tuple[str, str]]:
    """返回 [(条款号, 正文)]；识别不到条款时整篇作为一段。"""
    text = text.replace("\r\n", "\n").replace("\u3000", " ")
    pattern = ART_LINE if ART_LINE.search(text) else ART_INLINE
    marks = list(pattern.finditer(text))
    if not marks:
        return [("", text.strip())]

    result = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        if body:
            result.append((m.group(1), body))
    return result or [("", text.strip())]


def split_long(article: str, body: str) -> list[tuple[str, str]]:
    """超长条款按句号/分号切成多段，保证单条不超过 MAX_CHUNK_LEN。"""
    if len(body) <= config.MAX_CHUNK_LEN:
        return [(article, body)]
    sentences = re.split(r"(?<=[。；])", body)
    parts, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) > config.MAX_CHUNK_LEN and buf:
            parts.append(buf)
            buf = s
        else:
            buf += s
    if buf:
        parts.append(buf)
    if len(parts) == 1:
        return [(article, parts[0])]
    return [(f"{article}（{i + 1}/{len(parts)}）", p) for i, p in enumerate(parts)]


def build_chunks() -> list[dict]:
    files = sorted(p for p in config.RAW_DIR.glob("*") if p.suffix.lower() in SUPPORTED)
    if not files:
        raise SystemExit(f"data/raw 里没有可解析的文件（支持 {', '.join(sorted(SUPPORTED))}）")

    chunks = []
    for path in files:
        doc_id, _, name = path.stem.partition("_")
        if not name:
            doc_id, name = "", path.stem
        text = read_text(path)
        if not text.strip():
            print(f"[跳过] {path.name} 没有提取到文字（可能是扫描件）")
            continue

        count = 0
        for article, body in split_by_article(text):
            for art, piece in split_long(article, body):
                chunks.append({
                    "id": f"{doc_id}-{art}-{count}",
                    "text": piece,
                    "doc_id": doc_id,
                    "law_name": name,
                    "article": art or "全文",
                    "source": path.name,
                    "status": "现行有效",
                })
                count += 1
        print(f"[解析] {path.name} → {count} 段")
    return chunks


def build_index(chunks: list[dict]) -> None:
    import chromadb

    from retriever import embed_documents

    db = chromadb.PersistentClient(path=str(config.DB_DIR))
    try:
        db.delete_collection(config.COLLECTION)
    except Exception:
        pass
    col = db.create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})

    batch = 32
    for i in range(0, len(chunks), batch):
        group = chunks[i:i + batch]
        vectors = embed_documents([c["text"] for c in group])
        col.add(
            ids=[c["id"] for c in group],
            documents=[c["text"] for c in group],
            embeddings=vectors,
            metadatas=[{k: c[k] for k in ("doc_id", "law_name", "article", "source", "status")} for c in group],
        )
        print(f"[入库] {min(i + batch, len(chunks))}/{len(chunks)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-index", action="store_true", help="只切分，不写向量库")
    args = parser.parse_args()

    chunks = build_chunks()
    config.CHUNK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.CHUNK_FILE.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\n共 {len(chunks)} 段，已写入 {config.CHUNK_FILE}")
    longest = max(chunks, key=lambda c: len(c["text"]))
    print(f"最长一段 {len(longest['text'])} 字：{longest['id']} {longest['law_name']} {longest['article']}")
    print(f"样例：{chunks[0]['text'][:80]}...")

    if args.no_index:
        print("\n已跳过向量化（--no-index）")
        return

    build_index(chunks)
    print("\n向量库建好了，运行 app.py 就能提问。")


if __name__ == "__main__":
    main()
