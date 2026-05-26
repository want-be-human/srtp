"""共享的 OpenAI / DeepSeek 兼容客户端。

teacher.py 和 ai_analysis.py 都从这里取同一个实例，避免每个模块各维护一份
key 检查、base_url、超时配置——之前两份代码漂移过，一个限了 timeout 一个没限。
"""

from typing import Optional

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from config import AI_API_BASE_URL, AI_API_KEY

# DeepSeek 正常 4-8s 一次，留 12s 读上限给远端波动一点抗性。
# 调用方需要更短超时时（比如雷达页要 3s 出 fallback）在 create() 里另传。
_DEFAULT_TIMEOUT = httpx.Timeout(connect=3.0, read=12.0, write=5.0, pool=5.0)

_shared_client: Optional[OpenAI] = None
_init_failed = False


def get_shared_ai_client() -> Optional[OpenAI]:
    """懒加载共享 client。没配 key 或初始化失败都返回 None，调用方走 fallback。"""
    global _shared_client, _init_failed
    if _shared_client is not None:
        return _shared_client
    if _init_failed or not AI_API_KEY:
        return None
    try:
        _shared_client = OpenAI(
            api_key=AI_API_KEY,
            base_url=AI_API_BASE_URL,
            timeout=_DEFAULT_TIMEOUT,
        )
        return _shared_client
    except Exception as exc:
        print(f"AI 共享客户端初始化失败: {exc}")
        _init_failed = True
        return None


def classify_ai_error(exc: Exception) -> str:
    """把 OpenAI SDK 抛出的异常归成几个短 key，前端按 key 翻友好文案。

    返回值刻意不带敏感细节（不带 key 名、不带 url），前端直接展示。
    """
    if isinstance(exc, AuthenticationError):
        return "auth"
    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, RateLimitError):
        return "rate_limit"
    if isinstance(exc, APIConnectionError):
        return "network"
    return "unknown"
