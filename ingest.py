"""重建检索库：把「已发布」文档按条切块，写入 chunks.jsonl 与向量库。

用法：
    .venv\\Scripts\\python.exe ingest.py            解析 + 切分 + 建索引
    .venv\\Scripts\\python.exe ingest.py --no-index 只切分，不建索引（不需要 Key）
"""
import argparse
import json
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import config
import kb_store


def build_chunks() -> list[dict]:
    """从数据库读取已发布文档，逐篇切块；文件缺失的跳过。"""
    docs = kb_store.list_documents(status="已发布")
    if not docs:
        raise SystemExit("数据库中没有已发布文档。管理员登录后台入库并通过审核后，再运行本脚本。")

    chunks: list[dict] = []
    for doc in docs:
        try:
            pieces = kb_store.build_chunks_for(doc)
        except Exception as exc:
            print(f"[跳过] {doc['doc_id']}《{doc['law_name']}》：{exc}")
            continue
        chunks.extend(pieces)
        print(f"[解析] {doc['doc_id']}《{doc['law_name']}》{doc['doc_type']} → {len(pieces)} 段")
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
            metadatas=[
                {k: c.get(k, "") for k in ("doc_id", "law_name", "article", "source", "status", "doc_type", "doc_no", "source_url")}
                for c in group
            ],
        )
        print(f"[入库] {min(i + batch, len(chunks))}/{len(chunks)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-index", action="store_true", help="只切分，不写向量库")
    args = parser.parse_args()

    kb_store.init_db()
    kb_store.seed_from_raw()

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
