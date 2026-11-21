"""检索层：BM25 关键词召回 + 向量召回，用 RRF 融合。"""
import json

import jieba
from rank_bm25 import BM25Okapi

import config

_chunks: list[dict] | None = None
_bm25: BM25Okapi | None = None


def reload() -> None:
    """发布或废止文档后调用，丢掉旧的片段与 BM25 缓存。"""
    global _chunks, _bm25
    _chunks = None
    _bm25 = None


def get_chunks() -> list[dict]:
    global _chunks
    if _chunks is None:
        _chunks = [json.loads(line) for line in config.CHUNK_FILE.open(encoding="utf-8")]
    return _chunks


def _get_bm25() -> BM25Okapi:
    global _bm25
    if _bm25 is None:
        _bm25 = BM25Okapi([jieba.lcut(c["text"]) for c in get_chunks()])
    return _bm25


_embedder = None
# BGE 中文模型官方建议：查询语句加指令前缀能提升检索效果，文档侧不加
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def _get_embedder():
    global _embedder
    if _embedder is None:
        import os
        # 国内直连 HuggingFace 不稳，走镜像下载模型（只需下载一次）
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=config.EMBED_MODEL)
    return _embedder


def embed_documents(texts: list[str]) -> list[list[float]]:
    """把文档片段转成向量。首次调用会下载并加载本地模型。"""
    return [v.tolist() for v in _get_embedder().embed(texts)]


def _embed_query(text: str) -> list[float]:
    return embed_documents([QUERY_PREFIX + text])[0]


def bm25_search(query: str, top_k: int) -> list[dict]:
    """关键词召回。对“第几条”“押运员”这类精确词最有效，向量检索容易漏。"""
    scores = _get_bm25().get_scores(jieba.lcut(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    chunks = get_chunks()
    return [chunks[i] for i in order if scores[i] > 0]


def vector_search(query: str, top_k: int) -> list[dict]:
    import chromadb
    db = chromadb.PersistentClient(path=str(config.DB_DIR))
    col = db.get_collection(config.COLLECTION)
    res = col.query(
        query_embeddings=[_embed_query(query)],
        n_results=top_k,
        include=["documents", "metadatas"],
    )
    hits = []
    for cid, doc, meta in zip(res["ids"][0], res["documents"][0], res["metadatas"][0]):
        hits.append({"id": cid, "text": doc, **meta})
    return hits


def rrf_fuse(rank_lists: list[list[dict]], top_k: int) -> list[dict]:
    """Reciprocal Rank Fusion：只看名次不看分数，避免两路分数量纲不一致。"""
    scores: dict[str, float] = {}
    store: dict[str, dict] = {}
    for hits in rank_lists:
        for rank, hit in enumerate(hits):
            scores[hit["id"]] = scores.get(hit["id"], 0.0) + 1.0 / (config.RRF_K + rank + 1)
            store.setdefault(hit["id"], hit)
    order = sorted(scores, key=lambda k: scores[k], reverse=True)[:top_k]
    return [store[i] for i in order]


def retrieve(query: str, mode: str = "hybrid", top_k: int = config.TOP_K) -> list[dict]:
    if mode == "vector":
        return vector_search(query, top_k)
    if mode == "bm25":
        return bm25_search(query, top_k)
    return rrf_fuse(
        [bm25_search(query, config.RECALL_K), vector_search(query, config.RECALL_K)],
        top_k,
    )
