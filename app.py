"""Streamlit 界面：登录 → 智能问答 / 案情研判 / 文档库 / 知识管理。政务门户风格。"""
import html
import json
from datetime import datetime

import streamlit as st

import auth
import config
import kb_store
import ui_case
import ui_docs
import ui_manage
import ui_qa

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

/* 聊天气泡 —— Streamlit 1.67 已移除 data-test-role，改用 avatar testid 区分 */
[data-testid="stChatMessage"] { border-radius:8px !important; padding:4px 6px !important; }

/* 用户消息：政务蓝底白字 */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: var(--gov-blue) !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) * { color:#fff !important; }

/* AI 回答：黑底白字，手机端强制高对比 */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  background:#0a1929 !important; border:1px solid #1f3a5f !important;
  box-shadow:0 2px 8px rgba(0,0,0,.35) !important;
  color:#ffffff !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) * { color:#ffffff !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) strong,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) b {
  color:#ffd166 !important; font-weight:700 !important;
}
/* 兜底：不依赖 :has() 的浏览器，用 content 的 aria-label 命中 */
[data-testid="stChatMessageContent"][aria-label="Chat message from assistant"] {
  background:#0a1929 !important; border-radius:8px !important;
}
[data-testid="stChatMessageContent"][aria-label="Chat message from assistant"],
[data-testid="stChatMessageContent"][aria-label="Chat message from assistant"] * { color:#ffffff !important; }
[data-testid="stChatMessageContent"][aria-label="Chat message from user"],
[data-testid="stChatMessageContent"][aria-label="Chat message from user"] * { color:#ffffff !important; }

/* "查看引用"展开区也用深色，避免白底透出 */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stExpander"] {
  background:#0f2140 !important; border-color:#1f3a5f !important;
}

/* 固定模板答案卡片 */
.ans-card {
  background:#0f2140; border-left:4px solid var(--gov-red);
  border-radius:6px; padding:12px 16px; margin-bottom:10px;
  box-shadow:0 2px 8px rgba(0,0,0,.18);
}
.ans-head { font-size:13px; font-weight:700; color:#ffd166; letter-spacing:1px; }
.ans-body { font-size:14px; color:#e8eef7; line-height:1.85; margin-top:6px; word-break:break-word; }
.ans-conclusion { border-left-color:#d4a017; }
.ans-basis { border-left-color:#13569e; }
.ans-validity { border-left-color:#2e7d32; }
.ans-penalty { border-left-color:#c8161d; }
.ans-note { border-left-color:#6b7785; }

/* 引用卡片（深色气泡内） */
.cite-card {
  background:#13294a; border-left:4px solid var(--gov-red);
  border-radius:4px; padding:12px 16px; margin-bottom:12px;
  box-shadow:0 2px 6px rgba(0,0,0,.3);
}
.cite-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px; }
.cite-law { font-weight:700; color:#9ec5ff !important; font-size:15px; }
.cite-article { background:#1e3a6b !important; color:#cfe0ff !important; padding:2px 10px; border-radius:4px; font-size:12px; font-weight:600; }
.cite-status-valid { background:#14532d !important; color:#86efac !important; padding:2px 10px; border-radius:4px; font-size:11px; font-weight:600; }
.cite-status-invalid { background:#7f1d1d !important; color:#fca5a5 !important; padding:2px 10px; border-radius:4px; font-size:11px; font-weight:600; }
.cite-status-amend { background:#78350f !important; color:#fcd34d !important; padding:2px 10px; border-radius:4px; font-size:11px; font-weight:600; }
.cite-src { font-size:11px; color:#8aa0c0 !important; margin-bottom:6px; }
.cite-src a { color:#9ec5ff !important; }
.cite-text { font-size:13px; color:#e8eef7 !important; line-height:1.7; white-space:pre-wrap; }

/* 文档库行 */
.doc-row {
  background:#fff; border:1px solid #dbe3ef; border-left:4px solid var(--gov-blue);
  border-radius:6px; padding:12px 16px; margin-bottom:10px;
}
.doc-main { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.doc-name { font-weight:700; color:var(--gov-blue); font-size:14px; }
.doc-meta { font-size:11px; color:var(--muted); margin-top:6px; line-height:1.7; }

/* 登录卡片 */
.login-title { text-align:center; color:var(--gov-blue); font-size:24px; font-weight:900; letter-spacing:2px; }
.login-sub { text-align:center; color:var(--muted); font-size:12px; margin:6px 0 18px; }

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


def load_stats() -> tuple[int, int, int, dict[str, int]]:
    """法规篇数、条款片段数、提问次数、各类型篇数。"""
    laws, n = set(), 0
    try:
        for line in config.CHUNK_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                laws.add(c.get("doc_id") or c.get("law_name", ""))
                n += 1
    except Exception:
        pass
    try:
        by_type = {t: len(kb_store.list_documents(status="已发布", doc_type=t)) for t in config.DOC_TYPES}
    except Exception:
        by_type = {}
    queries = 0
    hist_file = config.ROOT / "data" / "search_history.json"
    if hist_file.exists():
        try:
            queries = len(json.loads(hist_file.read_text(encoding="utf-8")))
        except Exception:
            queries = 0
    return len(laws), n, queries, by_type


def render_login() -> None:
    st.markdown('<div class="gov-topline"></div>', unsafe_allow_html=True)
    st.markdown(
        """<div class="gov-header">
            <div class="gov-header-left">
                <div class="gov-emblem">🚛</div>
                <div>
                    <div class="gov-super">交通运输行业 · 道路运输安全监管智能辅助平台</div>
                    <div class="gov-title">道路运输安全 AI 知识库</div>
                </div>
            </div>
            <div class="gov-sub">权威法规 · 精准检索 · 条款溯源</div>
        </div>""",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown('<div class="login-title">用户登录</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-sub">管理员可维护知识库；临时访客仅可查询，不能修改数据</div>',
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("账号", placeholder="请输入账号")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            ok = st.form_submit_button("登 录", type="primary", use_container_width=True)
        if ok:
            user = auth.authenticate(username, password)
            if user:
                auth.login(user)
                st.rerun()
            else:
                st.error("账号或密码不正确")
        st.caption("演示账号：管理员 admin / admin123　·　访客 guest / guest123")


def render_header(user: dict) -> None:
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
            <div class="gov-sub">权威法规 · 精准检索 · 条款溯源<br/>{today}　|　当前身份：{html.escape(user['name'])}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="gov-notice">公　告：本系统基于现行公开法规构建，仅供学习研究与辅助参考，具体执法以有权机关发布的正式文本为准。</div>',
        unsafe_allow_html=True,
    )


def render_stats(laws: int, chunks: int, queries: int, by_type: dict[str, int]) -> None:
    cols = st.columns(4)
    cards = [
        (laws, "收录法规", "部 · 已发布入库", False),
        (chunks, "条款片段", "条 · 可溯源", True),
        (queries, "累计提问", "次 · 历史留存", False),
        ("HYBRID", "检索模式", "向量 + BM25 融合", True),
    ]
    for col, (num, label, foot, accent) in zip(cols, cards):
        cls = "stat-card accent" if accent else "stat-card"
        style = ' style="font-size:22px;padding-top:8px;"' if isinstance(num, str) else ""
        col.markdown(
            f'<div class="{cls}"><div class="stat-num"{style}>{num}</div>'
            f'<div class="stat-label">{label}</div><div class="stat-foot">{foot}</div></div>',
            unsafe_allow_html=True,
        )
    if by_type:
        summary = "　·　".join(f"{k} {v}" for k, v in by_type.items() if v)
        if summary:
            st.caption(f"语料构成：{summary}")


def main() -> None:
    kb_store.init_db()
    try:
        kb_store.seed_from_raw()
    except Exception:
        pass

    user = auth.current_user()
    if not user:
        render_login()
        st.stop()

    render_header(user)
    laws, chunks, queries, by_type = load_stats()
    render_stats(laws, chunks, queries, by_type)

    admin = auth.is_admin()
    pages = ["智能问答", "案情研判", "文档库"] + (["知识管理"] if admin else [])

    # 支持 ?page=案情研判 直达，只在首次进入时生效；
    # 之后以侧栏点击为准，否则每轮 rerun 都会被 URL 里的旧参数覆盖，导致点击无效
    if "nav" not in st.session_state:
        qp = st.query_params.get("page")
        st.session_state.nav = qp if qp in pages else pages[0]
    if st.session_state.nav not in pages:
        st.session_state.nav = pages[0]

    with st.sidebar:
        st.markdown('<div class="nav-title">当 前 身 份</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="nav-card"><div class="k">账号</div><div class="v">{html.escape(user["username"])}</div></div>'
            f'<div class="nav-card"><div class="k">角色</div><div class="v">{html.escape(user["name"])}（'
            f'{"可入库审核" if admin else "只读"}）</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="nav-title">功 能 导 航</div>', unsafe_allow_html=True)
        page = st.radio("功能", pages, key="nav", label_visibility="collapsed")
        if st.query_params.get("page") != page:
            st.query_params["page"] = page
        if st.button("退出登录", use_container_width=True, key="logout_btn"):
            auth.logout()
            st.rerun()

    if page == "智能问答":
        ui_qa.render()
    elif page == "案情研判":
        ui_case.render()
    elif page == "文档库":
        ui_docs.render()
    elif page == "知识管理":
        ui_manage.render(user=user["username"])

    st.markdown(
        """<div class="gov-footer">
            <div class="main">道路运输安全 AI 知识库</div>
            <div>主办单位：道路运输安全 AI 知识库项目组　　技术编程：TRAE/Streamlit/GitHub</div>
            <div>© 2026 道路运输安全 AI 知识库　|　仅供学习研究使用</div>
        </div>""",
        unsafe_allow_html=True,
    )


main()
