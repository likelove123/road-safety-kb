"""文档库（只读）：所有角色可查看已发布与已废止文档的元数据。"""
import html

import streamlit as st

import config
import kb_store


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
        st.markdown(
            f"""<div class="doc-row">
                <div class="doc-main">
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
                </div>
            </div>""",
            unsafe_allow_html=True,
        )
