"""批量评估：跑测试问题，记录检索命中与生成答案，输出 CSV 供人工打分与论文实验。

用法：
    python eval.py                    # 混合检索，跑全部题目
    python eval.py --mode vector      # 只跑向量检索
    python eval.py --mode bm25        # 只跑关键词检索
    python eval.py --limit 3          # 只跑前 3 题（调试用）

输出：data/eval_{mode}.csv
"""
import argparse
import csv
import json
import time

from openai import OpenAI

import config

PROMPT = """你是道路运输安全领域的法规问答助手。只能依据下面提供的【资料片段】回答。

规则：
1. 只使用片段里的内容，不得引入片段之外的法规或常识
2. 每个结论后标注出处，格式：（《法规名》第X条）
3. 片段里没有答案时，直接回答“现有资料中未找到相关条款”，禁止编造条款号
4. 用简洁的条目式中文，先给结论，再给依据

【资料片段】
{context}

【用户问题】
{question}"""


def build_context(hits: list[dict]) -> str:
    return "\n\n".join(
        "[片段%d]《%s》%s\n%s" % (i, h["law_name"], h["article"], h["text"])
        for i, h in enumerate(hits, 1)
    )


def ask(question: str, hits: list[dict]) -> str:
    client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL)
    resp = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": PROMPT.format(context=build_context(hits), question=question)}],
        temperature=0.1,
    )
    return resp.choices[0].message.content


def hit_at_k(hits: list[dict], gold_law: str, gold_article: str) -> str:
    """gold 没标注时返回“未标注”，标注了判断 Top5 是否命中。"""
    if not gold_article:
        return "未标注"
    for h in hits:
        if gold_law in h["law_name"] and gold_article in h["article"]:
            return "命中"
    return "未命中"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "vector", "bm25"])
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题，0 表示全部")
    args = parser.parse_args()

    from retriever import retrieve

    questions = json.loads((config.ROOT / "data" / "eval_questions.json").read_text(encoding="utf-8"))
    if args.limit:
        questions = questions[: args.limit]

    rows = []
    for i, q in enumerate(questions, 1):
        start = time.time()
        hits = retrieve(q["question"], mode=args.mode, top_k=config.TOP_K)
        answer = ask(q["question"], hits) if hits else "未检索到任何片段"
        cost = round(time.time() - start, 1)

        top1 = "%s %s" % (hits[0]["law_name"], hits[0]["article"]) if hits else "无"
        rows.append({
            "编号": q["id"],
            "分类": q["category"],
            "问题": q["question"],
            "检索命中": hit_at_k(hits, q["gold_law"], q["gold_article"]),
            "Top1出处": top1,
            "回答": answer.replace("\n", " "),
            "耗时秒": cost,
            "人工判定": "",
        })
        print("[%d/%d] %s 命中=%s 耗时=%ss" % (i, len(questions), q["id"], rows[-1]["检索命中"], cost))

    out = config.ROOT / "data" / ("eval_%s.csv" % args.mode)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    marked = [r for r in rows if r["检索命中"] != "未标注"]
    hits = sum(1 for r in marked if r["检索命中"] == "命中")
    avg = round(sum(r["耗时秒"] for r in rows) / len(rows), 1)
    no_answer = sum(1 for r in rows if "未找到" in r["回答"])

    print("\n===== 汇总（%s）=====" % args.mode)
    print("题目数：%d" % len(rows))
    print("平均耗时：%ss" % avg)
    print("回答“未找到”：%d 题" % no_answer)
    if marked:
        print("检索命中@5：%d/%d = %.0f%%" % (hits, len(marked), hits / len(marked) * 100))
    else:
        print("检索命中@5：gold 未标注，先填 eval_questions.json 的条款号")
    print("明细已写入：%s" % out)


if __name__ == "__main__":
    main()
