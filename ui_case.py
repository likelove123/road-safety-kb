"""案情研判页：输入简短案情，返回 3-5 条适用法规与处罚幅度。"""
import streamlit as st

import analyzer
import masking
from retriever import retrieve
from ui_common import render_answer, render_citations

EXAMPLE = (
    "2026年3月，某客运公司驾驶员驾驶粤B50321大型客车，核定载客45人，实际载客58人，"
    "在高速公路上行驶时被交警查获。驾驶员姓名：张伟，身份证430123456789012345。"
    "该公司未按规定对车辆进行动态监控，车载终端已离线3天。"
)


def render() -> None:
    st.markdown('<div class="section-title">案情研判</div>', unsafe_allow_html=True)
    st.caption("输入简要案情，系统检索现行法规并给出适用条款与处罚幅度；车牌、身份证、姓名自动脱敏。")

    top_k = st.slider("研判召回片段数", 5, 12, 8, key="case_topk")
    case_text = st.text_area(
        "案情描述",
        height=160,
        placeholder="例如：某客运公司客车核载45人实载58人，被交警查获，车辆动态监控终端离线3天……",
        key="case_input",
    )

    left, right = st.columns([1, 3])
    if left.button("开始研判", type="primary", use_container_width=True):
        if not case_text.strip():
            st.warning("请先输入案情描述")
        else:
            safe_case = masking.desensitize_case(case_text)
            with st.spinner("检索适用法规并生成研判意见…"):
                hits = retrieve(safe_case, mode="hybrid", top_k=top_k)
                answer = analyzer.analyze_case(safe_case, hits) if hits else (
                    "【案情摘要】已收到案情，但知识库中没有检索到相关条款。\n"
                    "【适用条款】无\n【处罚幅度】无法判断\n【说明】建议补充对应法规或细化案情关键词。"
                )
            st.session_state.case_result = {"case": safe_case, "answer": answer, "hits": hits}
    right.button(
        "填入示例案情",
        use_container_width=True,
        on_click=lambda: st.session_state.update(case_input=EXAMPLE),
    )

    result = st.session_state.get("case_result")
    if not result:
        st.info("提示：案情越具体（车型、载客/载货情况、道路类型、违法行为），检索与研判越准确。")
        return

    st.markdown('<div class="suggest-label">脱敏后的案情</div>', unsafe_allow_html=True)
    st.code(result["case"], language=None)

    render_answer(result["answer"])
    if result.get("hits"):
        with st.expander(f"查看引用的 {len(result['hits'])} 条原文", expanded=False):
            render_citations(result["hits"])
