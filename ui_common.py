"""界面公共组件：固定模板答案渲染、引用卡片、状态徽标。"""
import html
import re

import streamlit as st

import masking

SECTION_RE = re.compile(r"【([^】]{1,10})】")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

SECTION_STYLE = {
    "结论": "ans-conclusion",
    "案情摘要": "ans-conclusion",
    "依据": "ans-basis",
    "适用条款": "ans-basis",
    "效力": "ans-validity",
    "处罚幅度": "ans-penalty",
    "说明": "ans-note",
}


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """把【结论】…【依据】… 拆成 (引导语, [(标题, 正文)])。"""
    marks = list(SECTION_RE.finditer(text))
    if not marks:
        return text, []
    lead = text[: marks[0].start()].strip()
    out = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), text[start:end].strip()))
    return lead, out


def _rich(body: str) -> str:
    """转义 HTML，保留换行与加粗。"""
    body = html.escape(masking.mask_text(body))
    body = BOLD_RE.sub(r"<strong>\1</strong>", body)
    return body.replace("\n", "<br>")


def render_answer(text: str) -> None:
    """渲染固定模板答案：分块卡片，自动脱敏。"""
    text = masking.mask_text(text or "")
    lead, sections = split_sections(text)
    if not sections:
        st.markdown(text)
        return
    if lead:
        st.markdown(lead)
    for title, body in sections:
        cls = SECTION_STYLE.get(title, "ans-note")
        st.markdown(
            f'<div class="ans-card {cls}"><div class="ans-head">{html.escape(title)}</div>'
            f'<div class="ans-body">{_rich(body)}</div></div>',
            unsafe_allow_html=True,
        )


def status_class(status: str) -> str:
    if "废止" in status:
        return "cite-status-invalid"
    if "修订" in status:
        return "cite-status-amend"
    return "cite-status-valid"


def render_citations(hits: list[dict]) -> None:
    """检索片段渲染成可追溯的引用卡片。"""
    for i, h in enumerate(hits, 1):
        law = html.escape(h.get("law_name", ""))
        article = html.escape(h.get("article", ""))
        source = html.escape(h.get("source", ""))
        status = h.get("status", "")
        doc_type = h.get("doc_type", "")
        doc_no = h.get("doc_no", "")
        source_url = h.get("source_url", "")
        text = html.escape(masking.mask_text(h.get("text", ""))[:600])
        meta_bits = " · ".join(x for x in (doc_type, f"文号：{doc_no}" if doc_no else "") if x)
        src_line = f"来源文件：{source}"
        if meta_bits:
            src_line = f"{meta_bits}　|　{src_line}"
        if source_url:
            src_line += f'　|　<a href="{html.escape(source_url)}" target="_blank">原文链接</a>'
        st.markdown(
            f"""<div class="cite-card">
                <div class="cite-head">
                    <span class="cite-law">片段 {i}：《{law}》</span>
                    <span class="cite-article">{article}</span>
                    <span class="{status_class(status)}">{html.escape(status) or '状态未知'}</span>
                </div>
                <div class="cite-src">{src_line}</div>
                <div class="cite-text">{text}</div>
            </div>""",
            unsafe_allow_html=True,
        )
