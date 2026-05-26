# -*- coding: utf-8 -*-
"""
后端统一配置中心
================

所有配置项集中管理，包括：
- API密钥
- 数据库配置
- 服务端口
- YOLO模型路径
"""

import json
import os
from pathlib import Path

# ============================================
# 项目路径配置
# ============================================
BACKEND_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = BACKEND_DIR.parent

# ============================================
# AI API 配置 (统一使用 DeepSeek / OpenAI 兼容格式)
# ============================================
# key / base_url / model 都接受 AI_* 和 OPENAI_* 两套命名，谁有用谁，仨默认值都
# 兜底成 DeepSeek（OpenAI SDK 兼容协议，base_url 不带 /v1）
AI_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY")
    or os.environ.get("OPENAI_API_KEY", "")
)
AI_API_BASE_URL = (
    os.environ.get("AI_API_BASE_URL")
    or os.environ.get("OPENAI_BASE_URL")
    or "https://api.deepseek.com"
)
AI_MODEL = (
    os.environ.get("AI_MODEL")
    or os.environ.get("OPENAI_MODEL")
    or "deepseek-chat"
)

# ============================================
# 服务器配置
# ============================================
BACKEND_HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 8000))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# ============================================
# 数据库配置
# ============================================
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/welding.db")

# ============================================
# YOLO配置
# ============================================
YOLO_MODEL_PATH = os.environ.get(
    "YOLO_MODEL_PATH",
    str(BACKEND_DIR / "services" / "yolo" / "models" / "best.pt")
)
YOLO_CONFIDENCE_THRESHOLD = float(os.environ.get("YOLO_CONFIDENCE_THRESHOLD", 0.3))
YOLO_IOU_THRESHOLD = float(os.environ.get("YOLO_IOU_THRESHOLD", 0.45))

# 置信度、宽度阈值、各项打分权重等都在这个 json 里
YOLO_CONFIG_FILE = str(BACKEND_DIR / "yolo_config.json")


def _load_width_thresholds():
    try:
        with open(YOLO_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f).get("width_thresholds", {}) or {}
    except (OSError, json.JSONDecodeError):
        return {}


_W = _load_width_thresholds()
# 从 yolo_config.json::width_thresholds 同步出来的内存副本
OPTIMAL_WELD_WIDTH_MM = float(_W.get("optimal_width_mm", 5.5))
MIN_WELD_WIDTH_MM = float(_W.get("min_width_mm", 3.0))
MAX_WELD_WIDTH_MM = float(_W.get("max_width_mm", 8.0))

# ============================================
# CORS配置
# ============================================
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ============================================
# 功能开关
# ============================================
ENABLE_MOCK_DETECTION = os.environ.get("ENABLE_MOCK_DETECTION", "false").lower() == "true"
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# ============================================
# 辅助函数
# ============================================
def get_ai_config():
    """获取AI服务配置"""
    return {
        "api_key": AI_API_KEY,
        "base_url": AI_API_BASE_URL,
        "model": AI_MODEL
    }

def get_yolo_config():
    """获取YOLO配置"""
    return {
        "model_path": YOLO_MODEL_PATH,
        "confidence_threshold": YOLO_CONFIDENCE_THRESHOLD,
        "iou_threshold": YOLO_IOU_THRESHOLD
    }
