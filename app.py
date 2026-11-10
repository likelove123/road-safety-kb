"""Streamlit 界面：提问 → 混合检索 → 带条款引用的回答。"""
import streamlit as st
from openai import OpenAI

import config
from retriever import retrieve

st.set_page_config(page_title="道路运输安全 AI 知识库", page_icon="🚛", layout="wide")

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


st.title("道路运输安全 AI 知识库")
st.caption("答案均标注法规条款出处；未命中的问题会如实说明，不会编造条文。")

with st.sidebar:
    st.subheader("检索设置")
    mode_label = st.radio(
        "检索方式",
        ["混合检索（向量 + BM25）", "仅向量检索", "仅关键词检索"],
        help="对比实验用：切换不同检索方式，观察答案质量差异",
    )
    mode = {"混合检索（向量 + BM25）": "hybrid", "仅向量检索": "vector", "仅关键词检索": "bm25"}[mode_label]
    top_k = st.slider("召回片段数", 3, 10, config.TOP_K)
    st.divider()
    st.caption(f"对话模型：{config.CHAT_MODEL}")
    st.caption(f"向量模型：{config.EMBED_MODEL}")

if not config.API_KEY:
    st.error("还没有配置 API_KEY。把 .env.example 复制成 .env，填入 Key 后重开页面。")
    st.stop()

question = st.chat_input("例如：危险货物运输车上必须配押运人员吗？")
if question:
    st.chat_message("user").write(question)
    with st.spinner("检索法规中…"):
        try:
            hits = retrieve(question, mode=mode, top_k=top_k)
        except Exception as exc:
            st.error(f"检索失败：{exc}\n\n先运行 ingest.py 建好索引了吗？")
            st.stop()

    if not hits:
        st.warning("没有检索到相关条款，换一种问法试试。")
    else:
        with st.spinner("生成回答…"):
            try:
                answer = ask(question, hits)
            except Exception as exc:
                st.error(f"模型调用失败：{exc}")
                st.stop()
        st.chat_message("assistant").markdown(answer)

        with st.expander(f"查看引用的 {len(hits)} 条原文"):
            for i, h in enumerate(hits, 1):
                st.markdown(f"**片段 {i}：《{h['law_name']}》{h['article']}**（{h['status']}）")
                st.caption(f"来源文件：{h['source']}")
                st.text(h["text"][:600])
                st.divider()
