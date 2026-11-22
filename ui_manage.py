"""知识入库与管理（仅管理员）：上传/抓取 → 草稿 → 提交审核 → 发布 → 废止。"""
import html
from pathlib import Path

import streamlit as st

import config
import kb_store
import parsers
import ui_docs

UPLOAD_TYPES = ["pdf", "docx", "txt", "md"]


def _preview_blocks(path: str, doc_type: str) -> tuple[int, int]:
    """返回 (字数, 片段数)，用于入库前预览。"""
    text = parsers.read_file(Path(path))
    blocks = parsers.split_document(text, doc_type)
    return len(text), len(blocks)


def _tag(text: str, cls: str = "cite-article") -> str:
    return f'<span class="{cls}">{html.escape(text)}</span>'


def _doc_line(d: dict) -> str:
    return (
        f"<b>《{html.escape(d['law_name'])}》</b>　{_tag(d['doc_type'])}　"
        f"{_tag('文号：' + d['doc_no'] if d['doc_no'] else '文号未填')}　"
        f"{_tag(d['status'], 'cite-status-valid' if d['status'] == '已发布' else 'cite-status-invalid')}"
    )


def _new_entry(user: str) -> None:
    st.markdown("#### 新建入库")
    st.caption("支持上传 PDF / Word / TXT，或直接抓取网页正文；入库前按 MD5 自动查重。")

    source = st.radio("来源方式", ["上传文件", "网页抓取"], horizontal=True, key="ingest_source")
    uploaded = None
    url = ""
    if source == "上传文件":
        uploaded = st.file_uploader("选择文件", type=UPLOAD_TYPES, key="ingest_file")
        default_name = ""
        if uploaded:
            stem = uploaded.name.rsplit(".", 1)[0]
            prefix, _, rest = stem.partition("_")
            default_name = rest if prefix.isdigit() and rest else stem
    else:
        url = st.text_input("网页地址", placeholder="https://www.gov.cn/……", key="ingest_url")
        default_name = ""
        if st.button("抓取网页并预览", key="fetch_btn"):
            try:
                with st.spinner("正在抓取网页…"):
                    title, text = parsers.fetch_url(url)
                    path = kb_store.save_upload(f"{title[:40] or 'webpage'}.txt", text)
                st.session_state.web_preview = {"title": title, "text": text, "path": str(path), "url": url}
            except Exception as exc:
                st.error(f"抓取失败：{exc}")
        preview = st.session_state.get("web_preview")
        if preview:
            default_name = preview["title"][:60]
            st.info(f"已抓取：{preview['title']}　共 {len(preview['text'])} 字")

    st.markdown("##### 元数据")
    c1, c2 = st.columns(2)
    name = c1.text_input("文档名称 *", value=default_name, key="ingest_name")
    doc_type = c2.selectbox(
        "文档类型 *",
        config.DOC_TYPES,
        index=config.DOC_TYPES.index(parsers.infer_doc_type(default_name)) if default_name else 2,
        key="ingest_type",
    )
    c3, c4 = st.columns(2)
    doc_no = c3.text_input("文号", placeholder="如：交通运输部令2023年第3号", key="ingest_no")
    validity = c4.selectbox("效力状态", config.VALIDITIES, key="ingest_validity")
    c5, c6 = st.columns(2)
    issue_date = c5.text_input("生成（公布）日期", placeholder="2023-01-01", key="ingest_issue")
    repeal_date = c6.text_input("废止日期", placeholder="留空表示未废止", key="ingest_repeal")
    source_url = st.text_input("来源 URL", value=url, key="ingest_srcurl")
    note = st.text_area("备注（可选）", height=60, key="ingest_note")

    if st.button("保存到草稿箱", type="primary", key="save_draft"):
        if not name.strip():
            st.warning("请填写文档名称")
            return
        try:
            if uploaded is not None:
                path = kb_store.save_upload(uploaded.name, uploaded.getvalue())
            elif source == "网页抓取":
                preview = st.session_state.get("web_preview")
                if not preview:
                    st.warning("请先抓取网页")
                    return
                path = preview["path"]
            else:
                st.warning("请选择文件或抓取网页")
                return

            doc_id = kb_store.create_document(
                name, doc_type, path,
                doc_no=doc_no, validity=validity, issue_date=issue_date,
                repeal_date=repeal_date, source_url=source_url,
                source_kind="upload" if uploaded is not None else "web",
                created_by=user, note=note,
            )
            chars, blocks = _preview_blocks(path, doc_type)
            st.success(f"已存入草稿箱：文档编号 {doc_id}，正文 {chars} 字，预计切出 {blocks} 条片段")
            st.session_state.pop("web_preview", None)
        except kb_store.DuplicateDoc as dup:
            st.error(f"MD5 查重命中：{dup}")
            st.caption(f"已存在文档：{dup.existing.get('law_name')}（{dup.existing.get('doc_id')}，{dup.existing.get('status')}）")
        except Exception as exc:
            st.error(f"入库失败：{exc}")


def _drafts(user: str) -> None:
    st.markdown("#### 草稿箱")
    drafts = kb_store.list_documents(status="草稿")
    if not drafts:
        st.info("草稿箱为空。")
        return

    labels = {f"{d['doc_id']} · 《{d['law_name']}》 · {d['doc_type']}": d for d in drafts}
    pick = st.selectbox("选择草稿", list(labels), key="draft_pick")
    doc = labels[pick]
    st.markdown(_doc_line(doc), unsafe_allow_html=True)

    with st.form(f"edit_{doc['doc_id']}"):
        c1, c2 = st.columns(2)
        name = c1.text_input("文档名称", doc["law_name"])
        doc_type = c2.selectbox("类型", config.DOC_TYPES, index=config.DOC_TYPES.index(doc["doc_type"]))
        c3, c4 = st.columns(2)
        doc_no = c3.text_input("文号", doc["doc_no"])
        validity = c4.selectbox("效力状态", config.VALIDITIES, index=config.VALIDITIES.index(doc["validity"]))
        c5, c6 = st.columns(2)
        issue_date = c5.text_input("生成日期", doc["issue_date"])
        repeal_date = c6.text_input("废止日期", doc["repeal_date"])
        source_url = st.text_input("来源 URL", doc["source_url"])
        note = st.text_area("备注", doc["note"], height=60)
        saved = st.form_submit_button("保存修改")
    if saved:
        kb_store.update_meta(
            doc["doc_id"], law_name=name.strip(), doc_type=doc_type, doc_no=doc_no.strip(),
            validity=validity, issue_date=issue_date, repeal_date=repeal_date,
            source_url=source_url.strip(), note=note,
        )
        st.success("已保存")
        st.rerun()

    c1, c2 = st.columns(2)
    if c1.button("提交审核", type="primary", use_container_width=True, key="submit_review"):
        kb_store.submit_for_review(doc["doc_id"])
        st.success("已提交，等待管理员审核")
        st.rerun()
    if c2.button("删除草稿", use_container_width=True, key="del_draft"):
        try:
            kb_store.delete_document(doc["doc_id"])
            st.success("已删除")
            st.rerun()
        except Exception as exc:
            st.error(f"删除失败：{exc}")


def _review(user: str) -> None:
    st.markdown("#### 待审核")
    docs = kb_store.list_documents(status="待审核")
    if not docs:
        st.info("没有待审核文档。")
        return

    labels = {f"{d['doc_id']} · 《{d['law_name']}》 · {d['doc_type']}": d for d in docs}
    pick = st.selectbox("选择待审核文档", list(labels), key="review_pick")
    doc = labels[pick]
    st.markdown(_doc_line(doc), unsafe_allow_html=True)
    st.caption(
        f"生成日期：{doc['issue_date'] or '—'}　废止日期：{doc['repeal_date'] or '—'}　"
        f"来源：{doc['source_url'] or '—'}"
    )
    if st.button("预览文档内容", key="review_preview", use_container_width=True):
        ui_docs.show_preview(doc)
    note = st.text_input("审核意见（退回时填写）", key="review_note")

    c1, c2 = st.columns(2)
    if c1.button("审核通过并发布", type="primary", use_container_width=True, key="approve_btn"):
        try:
            with st.spinner("正在按条切块并写入检索库，首次可能较慢…"):
                n = kb_store.publish(doc["doc_id"], reviewer=user)
            st.success(f"已发布：《{doc['law_name']}》，切出 {n} 条片段，已进入检索库")
            st.rerun()
        except Exception as exc:
            st.error(f"发布失败：{exc}")
    if c2.button("退回草稿", use_container_width=True, key="reject_btn"):
        kb_store.reject(doc["doc_id"], user, note)
        st.warning("已退回草稿箱")
        st.rerun()


def _published(user: str) -> None:
    st.markdown("#### 已发布文档库")
    docs = kb_store.list_documents(status="已发布")
    st.caption(f"共 {len(docs)} 篇。废止后仍保留元数据与条款，用于追溯历史依据。")
    if not docs:
        return

    labels = {f"{d['doc_id']} · 《{d['law_name']}》 · {d['doc_type']} · {d['chunk_count']} 条": d for d in docs}
    pick = st.selectbox("选择文档", list(labels), key="pub_pick")
    doc = labels[pick]
    st.markdown(_doc_line(doc), unsafe_allow_html=True)
    st.caption(
        f"文号：{doc['doc_no'] or '—'}　生成日期：{doc['issue_date'] or '—'}　"
        f"条款片段：{doc['chunk_count']}　来源：{doc['source_url'] or '—'}"
    )
    if st.button("废止该文档", key="repeal_btn"):
        try:
            kb_store.repeal(doc["doc_id"], reviewer=user)
            st.success("已标记为已废止，检索结果会显示废止状态")
            st.rerun()
        except Exception as exc:
            st.error(f"废止失败：{exc}")


def _repealed() -> None:
    docs = kb_store.list_documents(status="已废止")
    st.markdown("#### 已废止")
    if not docs:
        st.info("暂无已废止文档。")
        return
    for d in docs:
        st.markdown(
            f"- 【{d['doc_id']}】《{html.escape(d['law_name'])}》{d['doc_type']}　"
            f"废止日期：{d['repeal_date'] or '—'}",
            unsafe_allow_html=True,
        )


def render(user: str = "") -> None:
    st.markdown('<div class="section-title">知识入库与审核</div>', unsafe_allow_html=True)
    counts = kb_store.counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("草稿", counts.get("草稿", 0))
    c2.metric("待审核", counts.get("待审核", 0))
    c3.metric("已发布", counts.get("已发布", 0))
    c4.metric("已废止", counts.get("已废止", 0))

    tabs = st.tabs(["新建入库", "草稿箱", "待审核", "已发布", "已废止"])
    with tabs[0]:
        _new_entry(user)
    with tabs[1]:
        _drafts(user)
    with tabs[2]:
        _review(user)
    with tabs[3]:
        _published(user)
    with tabs[4]:
        _repealed()
