"""Streamlit 界面：提问 → 混合检索 → 带条款引用的回答。政务门户风格。"""
import html
import json
from datetime import datetime

import streamlit as st
from openai import OpenAI

import config
from retriever import retrieve

st.set_page_config(page_title="道路运输安全 AI 知识库", page_icon="🚛", layout="wide")

# ----------------------------- 全局主题样式（政务门户风） -----------------------------
CSS = """
:root {
  --gov-blue:#0b3d7c;
  --gov-blue-2:#13569e;
  --gov-blue-light:#e8f0fb;
  --gov-red:#c8161d;
  --gov-red-light:#fdeced;
  --gov-gold:#d4a017;
  --bg:#eef2f8;
  --text:#1f2d3d;
  --muted:#6b7785;
}
* { font-family: "Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif; }
.stApp { background: var(--bg); }

/* 顶部红色细线（政府门户标志） */
.gov-topline {
  background: var(--gov-red);
  height: 4px;
  margin: -1rem -1rem 0 -1rem;
}

/* 顶部主横幅 */
.gov-header {
  background: linear-gradient(90deg, var(--gov-blue) 0%, var(--gov-blue-2) 100%);
  padding: 22px 36px;
  margin: 0 -1rem 0 -1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 3px solid var(--gov-red);
}
.gov-header-left { display:flex; align-items:center; gap:16px; }
.gov-emblem {
  width:56px; height:56px; border-radius:50%;
  background: rgba(255,255,255,.15);
  display:flex; align-items:center; justify-content:center;
  font-size:30px; border:2px solid rgba(255,255,255,.4);
}
.gov-super { color:#cfdcf0; font-size:13px; letter-spacing:2px; }
.gov-title { color:#fff; font-size:28px; font-weight:900; letter-spacing:2px; margin-top:2px; }
.gov-sub { color:#fff; font-size:13px; opacity:.9; text-align:right; line-height:1.8; }

/* 公告栏 */
.gov-notice {
  background: #fff8e6;
  border-left: 4px solid var(--gov-gold);
  color: #8a6d12;
  padding: 9px 18px;
  margin: 18px 0 16px;
  border-radius: 4px;
  font-size: 13px;
}

/* 数据指标卡 */
.stat-card {
  background:#fff;
  border-top:3px solid var(--gov-blue);
  border-radius:6px;
  padding:20px 16px;
  text-align:center;
  box-shadow:0 2px 10px rgba(11,61,124,.08);
  position:relative;
  height:120px;
}
.stat-card .stat-num { font-size:36px; font-weight:900; color:var(--gov-blue); line-height:1; }
.stat-card .stat-label { font-size:13px; color:var(--muted); margin-top:10px; font-weight:500; }
.stat-card .stat-foot { font-size:11px; color:#aab4c2; margin-top:6px; }
.stat-card.accent { border-top-color: var(--gov-red); }
.stat-card.accent .stat-num { color: var(--gov-red); }

/* 区块标题 */
.section-title {
  font-size:16px; font-weight:700; color:var(--gov-blue);
  border-left:4px solid var(--gov-red);
  padding-left:10px; margin: 24px 0 12px;
}

/* 侧边栏：功能导航 */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg,#0b3d7c 0%,#0e2f5a 100%) !important;
}
section[data-testid="stSidebar"] * { color:#e8eef7 !important; }
.nav-title {
  font-size:13px; letter-spacing:2px; color:#9fb6d6 !important;
  margin: 14px 0 8px; font-weight:600;
}
.nav-card {
  background: rgba(255,255,255,.07);
  border: 1px solid rgba(255,255,255,.12);
  border-radius:6px;
  padding: 10px 12px;
  margin-bottom:8px;
}
.nav-card .k { font-size:11px; opacity:.65; }
.nav-card .v { font-size:12px; font-weight:600; margin-top:3px; word-break:break-all; color:#fff !important; }

/* 建议问题按钮 */
.suggest-label { font-size:13px; color:var(--muted); margin-bottom:8px; font-weight:600; }
.suggest-btn button {
  background:#fff !important;
  border:1px solid #d6deec !important;
  border-radius:6px !important;
  color:var(--gov-blue) !important;
  font-weight:500 !important;
  padding:10px !important;
  text-align:left !important;
  height:auto !important; min-height:44px;
  transition:all .2s;
}
.suggest-btn button:hover {
  border-color:var(--gov-red) !important; color:var(--gov-red) !important;
  box-shadow:0 2px 8px rgba(200,22,29,.15) !important;
}

/* 历史搜索胶囊 */
.history-chip button {
  background:#f4f7fc !important;
  border:1px dashed #b8c6e0 !important;
  border-radius:999px !important;
  color:#3a4458 !important;
  font-size:12px !important;
  padding:3px 12px !important;
  height:auto !important; min-height:26px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.history-chip button:hover { border-color:var(--gov-red) !important; color:var(--gov-red) !important; }

/* 聊天气泡 */
[data-testid="stChatMessage"] { border-radius:8px !important; padding:4px 6px !important; }
[data-testid="stChatMessage"][data-test-role="user"] { background: var(--gov-blue) !important; }
[data-testid="stChatMessage"][data-test-role="user"] * { color:#fff !important; }
[data-testid="stChatMessage"][data-test-role="assistant"] {
  background:#fff !important; border:1px solid #e2e8f4;
  box-shadow:0 2px 8px rgba(11,61,124,.06);
}

/* 引用卡片 */
.cite-card {
  background:#fff; border-left:4px solid var(--gov-red);
  border-radius:4px; padding:12px 16px; margin-bottom:12px;
  box-shadow:0 2px 6px rgba(0,0,0,.05);
}
.cite-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px; }
.cite-law { font-weight:700; color:var(--gov-blue); font-size:15px; }
.cite-article { background:var(--gov-blue-light); color:var(--gov-blue-2); padding:2px 10px; border-radius:4px; font-size:12px; font-weight:600; }
.cite-status-valid { background:#e6f7ed; color:#1e8449; padding:2px 10px; border-radius:4px; font-size:11px; font-weight:600; }
.cite-status-invalid { background:var(--gov-red-light); color:var(--gov-red); padding:2px 10px; border-radius:4px; font-size:11px; font-weight:600; }
.cite-src { font-size:11px; color:#95a0b3; margin-bottom:6px; }
.cite-text { font-size:13px; color:#3a4458; line-height:1.7; white-space:pre-wrap; }

/* 页脚（政务风） */
.gov-footer {
  background: #0e2f5a;
  color:#a9b9d0;
  margin: 36px -1rem -1rem -1rem;
  padding: 22px 36px;
  text-align:center;
  font-size:12px;
  line-height:1.9;
}
.gov-footer .main { color:#cfdcf0; font-weight:600; }
"""
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

PROMPT = """你是道路运输安全领域的法规问答助手。只能依据下面提供的【资料片段】回答。

规则：
1. 只使用片段里的内容，不得引入片段之外的法规、标准或常识
2. 每个结论后标注出处，格式：（《法规名》第X条）
3. 片段里没有答案时，直接回答“现有资料中未找到相关条款”，并说明缺哪类资料，禁止编造条款号
4. 用简洁的条目式中文，先给结论，再给依据

【资料片段】
{context}

【用户问题】
{question}"""


def build_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[片段{i}] 来源：《{h['law_name']}》{h['article']}（{h['status']}）\n{h['text']}")
    return "\n\n".join(blocks)


def ask(question: str, hits: list[dict]) -> str:
    client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL)
    resp = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": PROMPT.format(context=build_context(hits), question=question)}],
        temperature=0.1,
    )
    return resp.choices[0].message.content


def load_stats() -> tuple[int, int]:
    """从切分文件读取真实统计：已收录法规数、条款片段数。"""
    laws, n = set(), 0
    try:
        for line in config.CHUNK_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                laws.add(c.get("law_name", ""))
                n += 1
    except Exception:
        pass
    return len(laws), n


def render_citations(hits: list[dict]) -> None:
    """把检索到的片段渲染成带状态徽标的引用卡片。"""
    for i, h in enumerate(hits, 1):
        law = html.escape(h.get("law_name", ""))
        article = html.escape(h.get("article", ""))
        source = html.escape(h.get("source", ""))
        status = h.get("status", "")
        text = html.escape(h.get("text", "")[:600])
        status_cls = "cite-status-valid" if "有效" in status else "cite-status-invalid"
        st.markdown(
            f"""<div class="cite-card">
                <div class="cite-head">
                    <span class="cite-law">片段 {i}：《{law}》</span>
                    <span class="cite-article">{article}</span>
                    <span class="{status_cls}">{html.escape(status) or '状态未知'}</span>
                </div>
                <div class="cite-src">来源文件：{source}</div>
                <div class="cite-text">{text}</div>
            </div>""",
            unsafe_allow_html=True,
        )


# ----------------------------- 政务顶栏 -----------------------------
today = datetime.now().strftime("%Y 年 %m 月 %d 日  %A")
st.markdown('<div class="gov-topline"></div>', unsafe_allow_html=True)
st.markdown(
    f"""<div class="gov-header">
        <div class="gov-header-left">
            <div class="gov-emblem">🚛</div>
            <div>
                <div class="gov-super">交通运输行业 · 道路运输安全监管智能辅助平台</div>
                <div class="gov-title">道路运输安全 AI 知识库</div>
            </div>
        </div>
        <div class="gov-sub">权威法规 · 精准检索 · 条款溯源<br/>{today}</div>
    </div>""",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="gov-notice">公　告：本系统基于现行公开法规构建，仅供学习研究与辅助参考，具体执法以有权机关发布的正式文本为准。</div>',
    unsafe_allow_html=True,
)

# ----------------------------- 数据指标卡 -----------------------------
total_laws, total_chunks = load_stats()
if "search_history" not in st.session_state:
    st.session_state.search_history = []
    hist_file = config.ROOT / "data" / "search_history.json"
    if hist_file.exists():
        try:
            st.session_state.search_history = json.loads(hist_file.read_text(encoding="utf-8"))
        except Exception:
            st.session_state.search_history = []
query_count = len(st.session_state.search_history)

stat_cols = st.columns(4)
with stat_cols[0]:
    st.markdown(f'<div class="stat-card"><div class="stat-num">{total_laws}</div><div class="stat-label">收录法规</div><div class="stat-foot">部 · 现行有效</div></div>', unsafe_allow_html=True)
with stat_cols[1]:
    st.markdown(f'<div class="stat-card accent"><div class="stat-num">{total_chunks}</div><div class="stat-label">条款片段</div><div class="stat-foot">条 · 可溯源</div></div>', unsafe_allow_html=True)
with stat_cols[2]:
    st.markdown(f'<div class="stat-card"><div class="stat-num">{query_count}</div><div class="stat-label">累计提问</div><div class="stat-foot">次 · 历史留存</div></div>', unsafe_allow_html=True)
with stat_cols[3]:
    st.markdown(f'<div class="stat-card accent"><div class="stat-num" style="font-size:22px;padding-top:8px;">HYBRID</div><div class="stat-label">检索模式</div><div class="stat-foot">向量 + BM25 融合</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">智能问答</div>', unsafe_allow_html=True)

# ----------------------------- 侧边栏：功能导航 -----------------------------
with st.sidebar:
    st.markdown('<div class="nav-title">系 统 导 航</div>', unsafe_allow_html=True)
    st.markdown("### 📚 法规问答")
    st.caption("输入问题，系统检索现行法规并标注条款出处。")

    st.markdown('<div class="nav-title">检 索 设 置</div>', unsafe_allow_html=True)
    mode_label = st.radio(
        "检索方式",
        ["混合检索（向量 + BM25）", "仅向量检索", "仅关键词检索"],
        help="对比实验用：切换不同检索方式，观察答案质量差异",
    )
    mode = {"混合检索（向量 + BM25）": "hybrid", "仅向量检索": "vector", "仅关键词检索": "bm25"}[mode_label]
    top_k = st.slider("召回片段数", 3, 10, config.TOP_K)

    st.markdown('<div class="nav-title">模 型 信 息</div>', unsafe_allow_html=True)
    st.markdown(
        f"""<div class="nav-card"><div class="k">对话模型</div><div class="v">{html.escape(config.CHAT_MODEL)}</div></div>
            <div class="nav-card"><div class="k">向量模型</div><div class="v">{html.escape(config.EMBED_MODEL)}</div></div>
            <div class="nav-card"><div class="k">运行方式</div><div class="v">本地向量化 · 数据不外传</div></div>""",
        unsafe_allow_html=True,
    )

if not config.API_KEY:
    st.error("还没有配置 API_KEY。把 .env.example 复制成 .env，填入 Key 后重开页面。")
    st.stop()

HISTORY_FILE = config.ROOT / "data" / "search_history.json"
MAX_HISTORY = 10


def save_history() -> None:
    """把搜索历史写入本地文件，刷新页面后仍然保留。"""
    try:
        HISTORY_FILE.write_text(
            json.dumps(st.session_state.search_history, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


# ----------------------------- 会话状态 -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

SUGGESTIONS = [
    "运输危险货物，车上必须配押运人员吗？",
    "驾驶员连续驾驶多长时间必须休息？",
    "营运客车多久做一次综合性能检测？",
    "动态监控发现超速报警，管理员该怎么处理？",
    "包车客运能不能沿途揽客？",
    "危险货物泄漏后第一现场怎么处置？",
]

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("hits"):
            with st.expander(f"查看引用的 {len(msg['hits'])} 条原文", expanded=False):
                render_citations(msg["hits"])

# 首屏无消息时显示建议问题
if not st.session_state.messages:
    st.markdown('<div class="suggest-label">热门问题（点击直接提问）</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for idx, q in enumerate(SUGGESTIONS):
        with cols[idx % 3]:
            st.markdown('<div class="suggest-btn">', unsafe_allow_html=True)
            if st.button(q, key=f"suggest_{idx}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# 历史搜索记录：展示在输入框上方，点击即可再次提问
if st.session_state.search_history:
    hbar = st.columns([5, 1])
    hbar[0].markdown('<div class="suggest-label">最近搜索（点击再次提问）</div>', unsafe_allow_html=True)
    if hbar[1].button("清空", key="clear_history", use_container_width=True):
        st.session_state.search_history = []
        save_history()
        st.rerun()
    shown = st.session_state.search_history[:MAX_HISTORY]
    chip_cols = st.columns(min(5, len(shown)))
    for i, hq in enumerate(shown):
        with chip_cols[i % min(5, len(shown))]:
            st.markdown('<div class="history-chip">', unsafe_allow_html=True)
            label = hq if len(hq) <= 14 else hq[:13] + "…"
            if st.button(label, key=f"hist_{i}", help=hq, use_container_width=True):
                st.session_state.pending_question = hq
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# 处理输入：建议问题或聊天框
pending = st.session_state.pop("pending_question", None)
question = st.chat_input("请输入道路运输安全相关问题，例如：危险货物运输必须配备押运人员吗？") or pending

if question:
    # 记入搜索历史：去重、最新排最前、限制条数
    hist = st.session_state.search_history
    if question in hist:
        hist.remove(question)
    hist.insert(0, question)
    st.session_state.search_history = hist[:MAX_HISTORY]
    save_history()

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.spinner("检索法规条款中…"):
        try:
            hits = retrieve(question, mode=mode, top_k=top_k)
        except Exception as exc:
            st.error(f"检索失败：{exc}\n\n先运行 ingest.py 建好索引了吗？")
            st.stop()

    if not hits:
        answer = "没有检索到相关条款，换一种问法试试，或补充相关法规到知识库。"
        st.session_state.messages.append({"role": "assistant", "content": answer, "hits": []})
        with st.chat_message("assistant"):
            st.warning(answer)
    else:
        with st.spinner("正在生成回答…"):
            try:
                answer = ask(question, hits)
            except Exception as exc:
                st.error(f"模型调用失败：{exc}")
                st.stop()
        st.session_state.messages.append({"role": "assistant", "content": answer, "hits": hits})
        with st.chat_message("assistant"):
            st.markdown(answer)
            with st.expander(f"查看引用的 {len(hits)} 条原文", expanded=False):
                render_citations(hits)

# ----------------------------- 政务页脚 -----------------------------
st.markdown(
    """<div class="gov-footer">
        <div class="main">道路运输安全 AI 知识库</div>
        <div>主办单位：道路运输安全 AI 知识库项目组　　技术编程：TRAE/Streamlit/GitHub</div>
        <div>© 2026 道路运输安全 AI 知识库　|　仅供学习研究使用</div>
    </div>""",
    unsafe_allow_html=True,
)
