"""智能问答页：混合检索 + 固定模板回答 + 条款溯源。"""
import json

import streamlit as st

import analyzer
import config
from retriever import retrieve
from ui_common import render_answer, render_citations

MAX_HISTORY = 10
HISTORY_FILE = config.ROOT / "data" / "search_history.json"

SUGGESTIONS = [
    "运输危险货物，车上必须配押运人员吗？",
    "驾驶员连续驾驶多长时间必须休息？",
    "营运客车多久做一次综合性能检测？",
    "动态监控发现超速报警，管理员该怎么处理？",
    "包车客运能不能沿途揽客？",
    "危险货物泄漏后第一现场怎么处置？",
]


def _load_history() -> list[str]:
    if "search_history" in st.session_state:
        return st.session_state.search_history
    data: list[str] = []
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = []
    st.session_state.search_history = data
    return data


def _save_history() -> None:
    try:
        HISTORY_FILE.write_text(
            json.dumps(st.session_state.search_history, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def _sidebar_settings() -> tuple[str, int]:
    st.sidebar.markdown('<div class="nav-title">检 索 设 置</div>', unsafe_allow_html=True)
    mode_label = st.sidebar.radio(
        "检索方式",
        ["混合检索（向量 + BM25）", "仅向量检索", "仅关键词检索"],
        key="qa_mode",
        help="对比实验用：切换检索方式，观察答案质量差异",
    )
    mode = {"混合检索（向量 + BM25）": "hybrid", "仅向量检索": "vector", "仅关键词检索": "bm25"}[mode_label]
    top_k = st.sidebar.slider("召回片段数", 3, 10, config.TOP_K, key="qa_topk")

    st.sidebar.markdown('<div class="nav-title">模 型 信 息</div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        f"""<div class="nav-card"><div class="k">对话模型</div><div class="v">{config.CHAT_MODEL}</div></div>
            <div class="nav-card"><div class="k">向量模型</div><div class="v">{config.EMBED_MODEL}</div></div>
            <div class="nav-card"><div class="k">运行方式</div><div class="v">本地向量化 · 数据不外传</div></div>""",
        unsafe_allow_html=True,
    )
    return mode, top_k


def render() -> None:
    mode, top_k = _sidebar_settings()

    st.markdown('<div class="section-title">智能问答</div>', unsafe_allow_html=True)
    st.caption("回答统一采用【结论】/【依据】/【效力】模板，依据可点击展开核对原文。")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    history = _load_history()

    # 历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                render_answer(msg["content"])
                if msg.get("hits"):
                    with st.expander(f"查看引用的 {len(msg['hits'])} 条原文", expanded=False):
                        render_citations(msg["hits"])
            else:
                st.markdown(msg["content"])

    # 首屏建议问题
    if not st.session_state.messages:
        st.markdown('<div class="suggest-label">热门问题（点击直接提问）</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        for idx, q in enumerate(SUGGESTIONS):
            with cols[idx % 3]:
                st.markdown('<div class="suggest-btn">', unsafe_allow_html=True)
                if st.button(q, key=f"suggest_{idx}", use_container_width=True):
                    st.session_state.pending_question = q
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # 最近搜索
    if history:
        hbar = st.columns([5, 1])
        hbar[0].markdown('<div class="suggest-label">最近搜索（点击再次提问）</div>', unsafe_allow_html=True)
        if hbar[1].button("清空", key="clear_history", use_container_width=True):
            st.session_state.search_history = []
            _save_history()
            st.rerun()
        shown = history[:MAX_HISTORY]
        chip_cols = st.columns(min(5, len(shown)))
        for i, hq in enumerate(shown):
            with chip_cols[i % min(5, len(shown))]:
                st.markdown('<div class="history-chip">', unsafe_allow_html=True)
                label = hq if len(hq) <= 14 else hq[:13] + "…"
                if st.button(label, key=f"hist_{i}", help=hq, use_container_width=True):
                    st.session_state.pending_question = hq
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("请输入道路运输安全相关问题，例如：危险货物运输必须配备押运人员吗？") or pending
    if not question:
        return

    hist = st.session_state.search_history
    if question in hist:
        hist.remove(question)
    hist.insert(0, question)
    st.session_state.search_history = hist[:MAX_HISTORY]
    _save_history()

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.spinner("检索法规条款中…"):
        try:
            hits = retrieve(question, mode=mode, top_k=top_k)
        except Exception as exc:
            st.error(f"检索失败：{exc}（先运行 ingest.py 建好索引）")
            st.stop()

    if not hits:
        answer = "【结论】现有资料中未找到相关条款，建议补充对应法规后再提问。\n【依据】无\n【效力】—"
        st.session_state.messages.append({"role": "assistant", "content": answer, "hits": []})
        with st.chat_message("assistant"):
            render_answer(answer)
        return

    with st.spinner("正在生成回答…"):
        try:
            answer = analyzer.ask(question, hits)
        except Exception as exc:
            st.error(f"模型调用失败：{exc}")
            st.stop()

    st.session_state.messages.append({"role": "assistant", "content": answer, "hits": hits})
    with st.chat_message("assistant"):
        render_answer(answer)
        with st.expander(f"查看引用的 {len(hits)} 条原文", expanded=False):
            render_citations(hits)
