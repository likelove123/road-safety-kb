"""文档库（只读）：所有角色可查看已发布与已废止文档的元数据，并支持预览与下载。"""
import html
from pathlib import Path

import streamlit as st

import config
import kb_store
import parsers

MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


@st.cache_data(show_spinner=False)
def _read_text(path_str: str, mtime: float) -> str:
    """读取原文文本（mtime 参与缓存键，文件更新后自动失效）。"""
    return parsers.read_file(Path(path_str))


@st.cache_data(show_spinner=False)
def _read_bytes(path_str: str, mtime: float) -> bytes:
    return Path(path_str).read_bytes()


def _source_path(doc: dict) -> Path | None:
    path = Path(doc.get("file_path") or "")
    return path if path.is_file() else None


def _doc_text(doc: dict) -> str:
    """优先读原始文件；文件缺失时退回用已切分的条款拼接。"""
    path = _source_path(doc)
    if path:
        try:
            text = _read_text(str(path), path.stat().st_mtime)
            if text.strip():
                return text
        except Exception:
            pass
    from retriever import get_chunks

    pieces = [
        f"{c.get('article', '')}\n{c['text']}"
        for c in get_chunks() if str(c.get("doc_id")) == str(doc["doc_id"])
    ]
    return "\n\n".join(pieces) or "（未找到原文，可能已被删除或尚未切分。）"


def _download_payload(doc: dict) -> tuple[bytes, str, str]:
    path = _source_path(doc)
    if path:
        suffix = path.suffix.lower()
        return _read_bytes(str(path), path.stat().st_mtime), f"{doc['law_name']}{suffix}", MIME.get(suffix, "text/plain")
    return _doc_text(doc).encode("utf-8"), f"{doc['law_name']}.txt", "text/plain"


@st.dialog("文档预览", width="large")
def _show_preview(doc: dict) -> None:
    status = "现行有效文档" if doc["status"] == "已发布" else "已废止文档"
    st.caption(
        f"《{doc['law_name']}》　·　{doc['doc_type']}　·　{doc['validity']}　·　{status}"
        "　·　预览为只读，不可编辑"
    )
    text = _doc_text(doc)
    limit = 40000
    if len(text) > limit:
        text = text[:limit] + "\n\n……（内容较长，仅显示前 4 万字，完整内容请点“下载”）"
    st.markdown(f'<div class="preview-box">{html.escape(text)}</div>', unsafe_allow_html=True)


def render() -> None:
    st.markdown('<div class="section-title">文档库</div>', unsafe_allow_html=True)
    st.caption("已发布文档供 AI 检索；已废止文档保留元数据，用于追溯历史依据。")

    docs = [d for d in kb_store.list_documents() if d["status"] in ("已发布", "已废止")]
    if not docs:
        st.info("文档库为空。")
        return

    c1, c2 = st.columns([1, 2])
    type_filter = c1.selectbox("按类型筛选", ["全部"] + config.DOC_TYPES, key="docs_type")
    kw = c2.text_input("搜索名称 / 文号", key="docs_kw")

    rows = [
        d for d in docs
        if (type_filter == "全部" or d["doc_type"] == type_filter)
        and (not kw or kw in d["law_name"] or kw in (d["doc_no"] or ""))
    ]

    st.markdown(
        f'<div class="suggest-label">共 {len(rows)} 篇（已发布 {sum(1 for d in rows if d["status"] == "已发布")} 篇）</div>',
        unsafe_allow_html=True,
    )

    for d in rows:
        status_cls = "cite-status-valid" if d["status"] == "已发布" else "cite-status-invalid"
        link = (
            f'<a href="{html.escape(d["source_url"])}" target="_blank">原文</a>'
            if d["source_url"] else "—"
        )
        with st.container(border=True):
            col_text, col_preview, col_download = st.columns([6, 1, 1], vertical_alignment="center")
            with col_text:
                st.markdown(
                    f"""<div class="doc-main">
                        <span class="doc-name">《{html.escape(d['law_name'])}》</span>
                        <span class="cite-article">{html.escape(d['doc_type'])}</span>
                        <span class="{status_cls}">{html.escape(d['validity'])}</span>
                    </div>
                    <div class="doc-meta">
                        文号：{html.escape(d['doc_no'] or '—')}　|　
                        条款片段：{d['chunk_count']}　|　
                        生成日期：{html.escape(d['issue_date'] or '—')}　|　
                        废止日期：{html.escape(d['repeal_date'] or '—')}　|　
                        来源：{link}
                    </div>""",
                    unsafe_allow_html=True,
                )
            if col_preview.button("预览", key=f"preview_{d['doc_id']}", use_container_width=True):
                _show_preview(d)
            data, filename, mime = _download_payload(d)
            col_download.download_button(
                "下载",
                data=data,
                file_name=filename,
                mime=mime,
                key=f"download_{d['doc_id']}",
                use_container_width=True,
            )
