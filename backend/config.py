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
# 支持两种环境变量命名方式，优先使用 DEEPSEEK_API_KEY
AI_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
# base_url 不需要 /v1 后缀，OpenAI SDK 会自动添加
AI_API_BASE_URL = os.environ.get("AI_API_BASE_URL", "https://api.deepseek.com")
AI_MODEL = os.environ.get("AI_MODEL", "deepseek-chat")

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
