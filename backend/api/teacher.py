import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from openai import OpenAI
import httpx

# 使用统一配置
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from config import AI_API_KEY, AI_API_BASE_URL, AI_MODEL

router = APIRouter()

_AI_TIMEOUT = httpx.Timeout(connect=3.0, read=12.0, write=5.0, pool=5.0)
_ai_client: Optional[OpenAI] = None


def _get_ai_client() -> Optional[OpenAI]:
    """惰性单例：避免每次请求重建 client、附带统一超时。"""
    global _ai_client
    if _ai_client is not None or not AI_API_KEY:
        return _ai_client
    try:
        _ai_client = OpenAI(
            api_key=AI_API_KEY,
            base_url=AI_API_BASE_URL,
            timeout=_AI_TIMEOUT,
        )
    except Exception as exc:
        print(f"AI 教师客户端初始化失败: {exc}")
        _ai_client = None
    return _ai_client


_FALLBACK_REPLY = (
    "AI 教师暂时无法响应。建议：检查焊缝表面光滑度（避免凸起或凹陷）、"
    "控制焊枪移动速度让焊缝宽度落在 4-6mm 之间、注意起弧/收弧避免气孔与裂纹。"
    "可以稍后再问，或直接查看预测页的本地建议。"
)

class ChatInput(BaseModel):
    message: str
    history: list = []
    context: Optional[Dict[str, Any]] = Field(default=None)

def format_context_for_prompt(context: Dict[str, Any]) -> str:
    """将检测结果上下文格式化为清晰的文本，以便AI理解。"""
    if not context:
        return ""
    
    score_lines = []
    if "skillScores" in context:
        for skill, score in context["skillScores"].items():
            score_lines.append(f"- {skill}: {score}分")
    
    scores_str = "\n".join(score_lines)
    
    prompt = f"""
背景信息：我刚刚完成了一次焊接练习，并得到了AI系统的检测报告。请根据以下报告内容，为我提供分析和改进建议。

[检测报告]
整体得分: {context.get('overallScore', 'N/A')}
技能维度评估:
{scores_str}
主要缺陷预测: {context.get('defectPrediction', {}).get('type', 'N/A')}

我的问题是：
"""
    return prompt

@router.post("/teacher/chat")
async def chat_with_teacher(payload: ChatInput):
    """
    与AI教师进行聊天，可以接收检测结果作为上下文。
    """
    client = _get_ai_client()
    if client is None:
        return {"response": _FALLBACK_REPLY, "fallback": True}

    messages = [{"role": "system", "content": "你是一个专业的焊接技术教学AI助手。你的任务是根据用户提供的检测报告和问题，给出具体、可行的分析和改进建议。"}]

    # 如果有上下文（检测结果），将其格式化并加到用户第一条消息前
    user_message = payload.message
    if payload.context and not payload.history: # 只在第一次对话时自动引入上下文
        context_prompt = format_context_for_prompt(payload.context)
        user_message = f"{context_prompt}{payload.message}"

    # 添加历史对话 - 支持两种格式
    for item in payload.history:
        # 格式1: {"role": "user/assistant", "content": "..."} (前端发送的格式)
        if item.get("role") and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
        # 格式2: {"user": "...", "assistant": "..."} (旧格式兼容)
        elif item.get("user"):
            messages.append({"role": "user", "content": item["user"]})
        elif item.get("assistant"):
            messages.append({"role": "assistant", "content": item["assistant"]})

    messages.append({"role": "user", "content": user_message})

    try:
        # openai 客户端是 sync 实现，直接 await 会阻塞 event loop——offload 到线程池
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=AI_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            stream=False,
        )
        ai_response = response.choices[0].message.content
        return {"response": ai_response}
    except Exception as e:
        print(f"AI 教师调用失败，使用本地兜底: {e}")
        return {"response": _FALLBACK_REPLY, "fallback": True, "error": str(e)}
