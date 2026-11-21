"""模型调用：固定模板问答 + 案情研判（3-5 条适用法规与处罚幅度）。"""
from openai import OpenAI

import config

QA_PROMPT = """你是道路运输安全领域的法规问答助手。只能依据下面提供的【资料片段】回答，禁止引入片段之外的法规或常识。

必须严格按以下模板输出，不要增减标题：
【结论】用一到两句话直接回答结论。
【依据】
1. 《法规名》第X条：该条与结论相关的原文要点。
2. 《法规名》第X条：……
【效力】现行有效（或 已修订 / 已废止）

规则：
1. 每条依据必须来自【资料片段】，条款号与法规名照抄片段，不得编造
2. 依据一般给 1-3 条，能支撑结论即可
3. 片段中没有答案时：【结论】现有资料中未找到相关条款，建议补充对应法规。【依据】无【效力】—
4. 语言简洁，不要输出模板以外的解释

【资料片段】
{context}

【用户问题】
{question}"""

CASE_PROMPT = """你是道路运输安全执法辅助助手。用户会给出一段简短案情，请依据【资料片段】给出适用法规和处罚幅度，禁止编造。

必须严格按以下模板输出：
【案情摘要】一句话概括违法行为。
【适用条款】
1. 《法规名》第X条（效力状态）：适用理由与条款要点。
2. 《法规名》第X条（效力状态）：……
【处罚幅度】引用条款中明确规定的罚款区间、责令改正、吊销证件、拘留等；若条款未写明幅度，写“所引条款未明确处罚幅度，需核对原文”。
【说明】执法提示或需进一步核实的事项。

规则：
1. 【适用条款】给 3-5 条，按相关性排序，必须来自【资料片段】
2. 处罚幅度只能照抄片段中的数字与措施，不得推算或编造
3. 案情中的车牌、身份证、姓名已脱敏，回答中不得还原
4. 若片段明显不足以支撑结论，在【说明】中指出缺少哪类依据

【资料片段】
{context}

【案件情况】
{case}"""


def build_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        head = f"[片段{i}] 来源：《{h.get('law_name', '')}》{h.get('article', '')}"
        if h.get("doc_no"):
            head += f"（文号：{h['doc_no']}）"
        head += f"（{h.get('status', '')}）"
        blocks.append(f"{head}\n{h.get('text', '')}")
    return "\n\n".join(blocks)


def _chat(prompt: str) -> str:
    client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL)
    resp = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""


def ask(question: str, hits: list[dict]) -> str:
    """法规问答，输出固定三段式模板。"""
    return _chat(QA_PROMPT.format(context=build_context(hits), question=question))


def analyze_case(case_text: str, hits: list[dict]) -> str:
    """案情研判，输出 3-5 条适用法规与处罚幅度。"""
    return _chat(CASE_PROMPT.format(context=build_context(hits), case=case_text))
