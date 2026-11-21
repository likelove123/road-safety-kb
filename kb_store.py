"""知识库文档层：SQLite 存元数据与审核流程，发布时按条切块写入检索库。

流程：草稿 → 待审核 → 已发布 → 已废止
"""
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import config
import masking
import parsers

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    law_name     TEXT NOT NULL,
    doc_type     TEXT NOT NULL DEFAULT '部门规章',
    doc_no       TEXT DEFAULT '',
    validity     TEXT NOT NULL DEFAULT '现行有效',
    issue_date   TEXT DEFAULT '',
    repeal_date  TEXT DEFAULT '',
    source_url   TEXT DEFAULT '',
    md5          TEXT UNIQUE,
    file_path    TEXT DEFAULT '',
    source_kind  TEXT DEFAULT 'upload',
    status       TEXT NOT NULL DEFAULT '草稿',
    created_by   TEXT DEFAULT '',
    created_at   TEXT DEFAULT '',
    reviewed_by  TEXT DEFAULT '',
    reviewed_at  TEXT DEFAULT '',
    review_note  TEXT DEFAULT '',
    chunk_count  INTEGER DEFAULT 0,
    note         TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
"""

FIELDS = (
    "law_name", "doc_type", "doc_no", "validity", "issue_date", "repeal_date",
    "source_url", "file_path", "source_kind", "status", "created_by", "created_at",
    "reviewed_by", "reviewed_at", "review_note", "chunk_count", "note",
)


class DuplicateDoc(Exception):
    """MD5 命中已有文档。"""

    def __init__(self, existing: dict):
        self.existing = existing
        super().__init__(f"内容重复：已存在《{existing.get('law_name', '')}》（{existing.get('doc_id', '')}）")


def _connect() -> sqlite3.Connection:
    config.KB_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.KB_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md5_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def find_by_md5(md5: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM documents WHERE md5 = ?", (md5,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_document(doc_id: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_documents(status: str | None = None, doc_type: str | None = None, keyword: str = "") -> list[dict]:
    sql = "SELECT * FROM documents WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if doc_type:
        sql += " AND doc_type = ?"
        args.append(doc_type)
    if keyword:
        sql += " AND (law_name LIKE ? OR doc_no LIKE ? OR note LIKE ?)"
        args += [f"%{keyword}%"] * 3
    sql += " ORDER BY created_at DESC, doc_id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def counts() -> dict[str, int]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM documents GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}
    finally:
        conn.close()


def _next_doc_id() -> str:
    conn = _connect()
    try:
        rows = conn.execute("SELECT doc_id FROM documents").fetchall()
    finally:
        conn.close()
    nums = [int(r["doc_id"]) for r in rows if str(r["doc_id"]).isdigit()]
    return f"{max(nums, default=0) + 1:02d}"


def save_upload(filename: str, data: bytes | str) -> Path:
    """把上传内容落到 data/uploads，返回文件路径。"""
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", Path(filename).name)
    path = config.UPLOAD_DIR / f"{datetime.now():%Y%m%d%H%M%S}_{safe}"
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def create_document(
    law_name: str,
    doc_type: str,
    file_path: str | Path,
    *,
    doc_no: str = "",
    validity: str = "现行有效",
    issue_date: str = "",
    repeal_date: str = "",
    source_url: str = "",
    source_kind: str = "upload",
    created_by: str = "",
    note: str = "",
    status: str = "草稿",
) -> str:
    """新建文档（默认进草稿箱）。MD5 重复时抛 DuplicateDoc。"""
    law_name = law_name.strip()
    if not law_name:
        raise ValueError("文档名称不能为空")
    path = Path(file_path)
    md5 = md5_file(path)
    dup = find_by_md5(md5)
    if dup:
        raise DuplicateDoc(dup)

    doc_id = _next_doc_id()
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO documents
               (doc_id, law_name, doc_type, doc_no, validity, issue_date, repeal_date,
                source_url, md5, file_path, source_kind, status, created_by, created_at, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id, law_name, doc_type, doc_no.strip(), validity, issue_date, repeal_date,
                source_url.strip(), md5, str(path), source_kind, status, created_by, _now(), note.strip(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return doc_id


def update_meta(doc_id: str, **fields) -> None:
    """更新允许编辑的元数据字段。"""
    clean = {k: v for k, v in fields.items() if k in FIELDS}
    if not clean:
        return
    sets = ", ".join(f"{k} = ?" for k in clean)
    conn = _connect()
    try:
        conn.execute(f"UPDATE documents SET {sets} WHERE doc_id = ?", (*clean.values(), doc_id))
        conn.commit()
    finally:
        conn.close()


def submit_for_review(doc_id: str) -> None:
    update_meta(doc_id, status="待审核", review_note="")


def reject(doc_id: str, reviewer: str, note: str = "") -> None:
    update_meta(doc_id, status="草稿", reviewed_by=reviewer, reviewed_at=_now(), review_note=note)


def delete_document(doc_id: str) -> None:
    doc = get_document(doc_id)
    if not doc:
        return
    if doc["status"] not in ("草稿", "已废止"):
        raise ValueError("只有草稿或已废止的文档可以删除")
    conn = _connect()
    try:
        conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()
    for p in (Path(doc["file_path"]) if doc["file_path"] else None,):
        if p and p.exists() and config.UPLOAD_DIR in p.parents:
            try:
                p.unlink()
            except OSError:
                pass


# ----------------------------- 发布 / 废止 -----------------------------

def _build_chunks(doc: dict) -> list[dict]:
    path = Path(doc["file_path"])
    if not path.exists():
        raise FileNotFoundError(f"原始文件不存在：{path}")
    text = parsers.read_file(path)
    blocks = parsers.split_document(text, doc["doc_type"])
    if not blocks:
        raise ValueError("没有解析出可用内容，请检查文件是否为扫描件")

    chunks = []
    for i, (label, body) in enumerate(blocks):
        if doc["doc_type"] in ("案例", "行政处罚决定"):
            body = masking.mask_text(body)  # 案例类入库即脱敏
        chunks.append({
            "id": f"{doc['doc_id']}-{label}-{i}",
            "text": body,
            "doc_id": doc["doc_id"],
            "law_name": doc["law_name"],
            "article": label,
            "source": path.name,
            "status": doc["validity"],
            "doc_type": doc["doc_type"],
            "doc_no": doc["doc_no"],
            "source_url": doc["source_url"],
        })
    return chunks


def build_chunks_for(doc: dict) -> list[dict]:
    """对外暴露：把一篇文档切成片段（不写库）。"""
    return _build_chunks(doc)


def _write_chunks(chunks: list[dict], doc_id: str) -> None:
    """把文档片段追加进 chunks.jsonl（先清掉该文档旧片段）。"""
    existing = []
    if config.CHUNK_FILE.exists():
        for line in config.CHUNK_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("doc_id") != doc_id:
                existing.append(row)
    existing.extend(chunks)
    config.CHUNK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.CHUNK_FILE.open("w", encoding="utf-8") as f:
        for row in existing:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _index_chunks(chunks: list[dict]) -> None:
    import chromadb

    from retriever import embed_documents

    db = chromadb.PersistentClient(path=str(config.DB_DIR))
    try:
        col = db.get_collection(config.COLLECTION)
    except Exception:
        col = db.create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})

    doc_id = chunks[0]["doc_id"]
    # 同 id 重新发布时先清旧向量，避免重复
    try:
        col.delete(where={"doc_id": doc_id})
    except Exception:
        pass

    batch = 32
    for i in range(0, len(chunks), batch):
        group = chunks[i:i + batch]
        col.add(
            ids=[c["id"] for c in group],
            documents=[c["text"] for c in group],
            embeddings=embed_documents([c["text"] for c in group]),
            metadatas=[
                {k: c[k] for k in ("doc_id", "law_name", "article", "source", "status", "doc_type", "doc_no", "source_url")}
                for c in group
            ],
        )


def publish(doc_id: str, reviewer: str = "") -> int:
    """审核通过：按条切块、写入检索库，状态置为已发布。返回片段数。"""
    doc = get_document(doc_id)
    if not doc:
        raise ValueError("文档不存在")
    if doc["status"] not in ("待审核", "草稿", "已发布"):
        raise ValueError(f"当前状态（{doc['status']}）不能发布")
    if doc["validity"] == "已废止":
        doc["validity"] = "现行有效"

    chunks = _build_chunks(doc)
    _write_chunks(chunks, doc_id)
    _index_chunks(chunks)
    try:
        import retriever

        retriever.reload()
    except Exception:
        pass
    update_meta(
        doc_id,
        status="已发布",
        validity=doc["validity"] if doc["validity"] != "已废止" else "现行有效",
        reviewed_by=reviewer,
        reviewed_at=_now(),
        chunk_count=len(chunks),
    )
    return len(chunks)


def repeal(doc_id: str, reviewer: str = "") -> None:
    """废止：标记文档与全部片段为已废止，保留可追溯性。"""
    doc = get_document(doc_id)
    if not doc:
        raise ValueError("文档不存在")
    update_meta(
        doc_id,
        status="已废止",
        validity="已废止",
        repeal_date=doc["repeal_date"] or datetime.now().strftime("%Y-%m-%d"),
        reviewed_by=reviewer,
        reviewed_at=_now(),
    )

    # 更新 chunks.jsonl
    if config.CHUNK_FILE.exists():
        rows = []
        for line in config.CHUNK_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("doc_id") == doc_id:
                row["status"] = "已废止"
            rows.append(row)
        with config.CHUNK_FILE.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 更新向量库元数据
    try:
        import chromadb

        db = chromadb.PersistentClient(path=str(config.DB_DIR))
        col = db.get_collection(config.COLLECTION)
        got = col.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids, metas = got.get("ids", []), got.get("metadatas", [])
        if ids:
            col.update(ids=ids, metadatas=[{**(m or {}), "status": "已废止"} for m in metas])
    except Exception:
        pass

    # 丢掉 BM25 缓存，避免继续召回旧状态
    try:
        import retriever

        retriever.reload()
    except Exception:
        pass


def seed_from_raw() -> int:
    """把 data/raw 下已有法规登记进数据库（幂等），保证老语料也能走审核与废止流程。"""
    seeded = 0
    counts: dict[str, int] = {}
    if config.CHUNK_FILE.exists():
        for line in config.CHUNK_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                counts[row.get("doc_id")] = counts.get(row.get("doc_id"), 0) + 1

    files = sorted(p for p in config.RAW_DIR.glob("*") if p.suffix.lower() in parsers.SUPPORTED)
    for path in files:
        if get_by_file(str(path)):
            continue
        prefix, _, name = path.stem.partition("_")
        doc_id = prefix if prefix.isdigit() else _next_doc_id()
        if get_document(doc_id):
            doc_id = _next_doc_id()
        name = name or path.stem
        md5 = md5_file(path)
        if find_by_md5(md5):
            continue
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO documents
                   (doc_id, law_name, doc_type, validity, md5, file_path, source_kind, status,
                    created_by, created_at, reviewed_by, reviewed_at, chunk_count)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    doc_id, name, parsers.infer_doc_type(name), "现行有效", md5, str(path),
                    "seed", "已发布", "system", _now(), "system", _now(), counts.get(doc_id, 0),
                ),
            )
            conn.commit()
            seeded += 1
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    return seeded


def get_by_file(file_path: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM documents WHERE file_path = ?", (file_path,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
