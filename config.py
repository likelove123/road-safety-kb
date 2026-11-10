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
