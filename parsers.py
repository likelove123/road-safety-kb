"""文档解析与切块：PDF / Word / 文本 / 网页，按“条”或章节切分，绝不整篇入库。"""
import re
from html.parser import HTMLParser
from pathlib import Path

import config

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}

# 法规条款起始：行首“第X条”
ART_LINE = re.compile(r"(?m)^\s*(第[一二三四五六七八九十百千零〇两0-9]+条)\s*")
# PDF 提取后可能没有换行
ART_INLINE = re.compile(r"(第[一二三四五六七八九十百千零〇两0-9]+条)[\s　]+")
# 案例、处罚决定的中文小标题：一、基本情况
CN_HEADING = re.compile(r"(?m)^\s*([一二三四五六七八九十]+、)\s*([^\n]{2,40})$")
# 标准、办事指南的编号标题：4.1 车辆要求 / 1 范围
NUM_HEADING = re.compile(r"(?m)^\s*(\d+(?:\.\d+){0,3})\s+([^\n]{2,40})$")


def read_file(path: Path) -> str:
    """读取本地文件文本。"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        import docx

        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    return Path(path).read_text(encoding="utf-8", errors="ignore")


class _HTMLText(HTMLParser):
    """极简网页正文提取，避免引入额外的 HTML 解析依赖。"""

    SKIP = {"script", "style", "noscript", "svg", "iframe"}
    BREAK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.in_title = False
        self.title = ""
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.title += data
        else:
            self.parts.append(data)


def fetch_url(url: str, timeout: int = 20) -> tuple[str, str]:
    """抓取网页，返回 (标题, 正文)。"""
    import requests

    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; RoadSafetyKB/1.0)"},
    )
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    parser = _HTMLText()
    parser.feed(resp.text)
    lines = [ln.strip() for ln in "".join(parser.parts).splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return (parser.title.strip() or url), text


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _split_by_article(text: str) -> list[tuple[str, str]]:
    """按“第X条”切分，每个条款一段。"""
    pattern = ART_LINE if ART_LINE.search(text) else ART_INLINE
    marks = list(pattern.finditer(text))
    if not marks:
        return []
    result = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        if body:
            result.append((m.group(1), body))
    return result


def _split_by_heading(text: str, pattern: re.Pattern) -> list[tuple[str, str]]:
    """按中文小标题或编号小标题切分，标题本身作为片段名。"""
    marks = list(pattern.finditer(text))
    if not marks:
        return []
    result = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        label = (m.group(1) + (m.group(2) if m.lastindex and m.lastindex >= 2 else "")).strip()
        if body:
            result.append((label, body))
    # 小标题之前若有引言，单独成段
    lead = text[: marks[0].start()].strip()
    if lead:
        result.insert(0, ("引言", lead))
    return result


def _split_by_paragraph(text: str) -> list[tuple[str, str]]:
    """兜底：按自然段聚合，保证每段不超过 MAX_CHUNK_LEN，不整篇成块。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    parts, buf = [], ""
    for p in paragraphs:
        if buf and len(buf) + len(p) + 1 > config.MAX_CHUNK_LEN:
            parts.append(buf)
            buf = p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf:
        parts.append(buf)
    if len(parts) <= 1:
        return [("全文", parts[0])] if parts else []
    return [(f"段落{i + 1}", p) for i, p in enumerate(parts)]


def _split_long(article: str, body: str) -> list[tuple[str, str]]:
    """超长条款按句号/分号切开，仍在同一条下编号。"""
    if len(body) <= config.MAX_CHUNK_LEN:
        return [(article, body)]
    sentences = re.split(r"(?<=[。；])", body)
    parts, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) > config.MAX_CHUNK_LEN and buf:
            parts.append(buf)
            buf = s
        else:
            buf += s
    if buf:
        parts.append(buf)
    if len(parts) == 1:
        return [(article, parts[0])]
    return [(f"{article}（{i + 1}/{len(parts)}）", p) for i, p in enumerate(parts)]


def split_document(text: str, doc_type: str = "") -> list[tuple[str, str]]:
    """按文档类型选择切分策略，返回 [(片段名, 正文)]。

    法规类一律按“条”切；案例/处罚决定按小标题切；标准与指南按编号标题切。
    """
    text = _normalize(text)
    if not text:
        return []

    if doc_type in ("案例", "行政处罚决定"):
        blocks = _split_by_heading(text, CN_HEADING) or _split_by_heading(text, NUM_HEADING)
    elif doc_type in ("行业标准", "办事指南"):
        blocks = _split_by_heading(text, NUM_HEADING) or _split_by_heading(text, CN_HEADING)
    else:
        blocks = _split_by_article(text)
        if not blocks:
            blocks = _split_by_heading(text, NUM_HEADING) or _split_by_heading(text, CN_HEADING)

    if not blocks:
        blocks = _split_by_paragraph(text)

    result: list[tuple[str, str]] = []
    for label, body in blocks:
        result.extend(_split_long(label, body))
    return result


def infer_doc_type(name: str) -> str:
    """按文件名猜文档类型，减少入库时的手工选择。"""
    if "案例" in name:
        return "案例"
    if "处罚决定" in name or name.endswith("决定书") or name.startswith("行政处罚"):
        return "行政处罚决定"
    if "办事指南" in name:
        return "办事指南"
    if re.search(r"(GB|JT/?T|JTG|AQ/?T|标准)", name, re.I):
        return "行业标准"
    if name.endswith("法") and not name.endswith(("办法", "方法", "做法", "说法")) and "条例" not in name:
        return "法律"
    if re.match(r"^(北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|内蒙古|广西|西藏|宁夏|新疆)", name):
        return "地方性法规"
    if "条例" in name:
        return "行政法规"
    return "部门规章"
