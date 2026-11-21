"""全局配置与路径。所有脚本都从这里取配置，不要写死在业务代码里。"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    """优先读 Streamlit Cloud 的 secrets，本地回落到 .env，都没配就用默认值。"""
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return (os.getenv(key) or default).strip()


# 目录
RAW_DIR = ROOT / "data" / "raw"
CHUNK_FILE = ROOT / "data" / "chunks.jsonl"
DB_DIR = ROOT / "data" / "chroma"
COLLECTION = "road_safety"
KB_DB = ROOT / "data" / "kb.db"          # 文档元数据与审核流程（SQLite）
UPLOAD_DIR = ROOT / "data" / "uploads"    # 后台上传的原始文件
SAMPLE_DIR = ROOT / "data" / "samples"    # 示例文档（用于演示入库流程）

# 文档类型、效力与审核状态（顺序即界面下拉顺序）
DOC_TYPES = ["法律", "行政法规", "部门规章", "地方性法规", "行业标准", "办事指南", "案例", "行政处罚决定"]
VALIDITIES = ["现行有效", "已修订", "已废止"]
WORKFLOW = ["草稿", "待审核", "已发布", "已废止"]

# 极简登录账号（云端可在 secrets 里覆盖）
ADMIN_USER = _get("ADMIN_USER", "admin")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "admin123")
GUEST_USER = _get("GUEST_USER", "guest")
GUEST_PASSWORD = _get("GUEST_PASSWORD", "guest123")

# 对话模型（DeepSeek，OpenAI 兼容接口）
API_KEY = _get("API_KEY")
BASE_URL = _get("BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = _get("CHAT_MODEL", "deepseek-chat")

# 向量模型（本地跑，不需要 Key，不产生费用）
EMBED_MODEL = _get("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
EMBED_DEVICE = "cpu"

# 检索参数
TOP_K = 5          # 最终给模型的片段数
RECALL_K = 20      # 单路召回数量
RRF_K = 60         # RRF 平滑常数

# 切分参数
MAX_CHUNK_LEN = 800
