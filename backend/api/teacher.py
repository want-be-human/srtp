import asyncio
import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# 让 api/teacher.py 能 import 到上一层 backend 下的 config / ai_client
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from ai_client import classify_ai_error, get_shared_ai_client
from config import AI_MODEL

router = APIRouter()


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
    """把检测结果上下文格式化成文本，便于 LLM 一次拿到完整背景。"""
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
    """与 AI 教师对话；失败时返回 fallback 文案，但带 error_category 让前端能展示具体原因。"""
    client = get_shared_ai_client()
    if client is None:
        return {
            "response": _FALLBACK_REPLY,
            "fallback": True,
            "error_category": "not_configured",
        }

    messages = [
        {
            "role": "system",
            "content": "你是一个专业的焊接技术教学AI助手。你的任务是根据用户提供的检测报告和问题，给出具体、可行的分析和改进建议。",
        }
    ]

    user_message = payload.message
    if payload.context and not payload.history:  # 第一次对话才自动引入上下文
        context_prompt = format_context_for_prompt(payload.context)
        user_message = f"{context_prompt}{payload.message}"

    # 兼容两种历史格式：前端发的 {role, content} 和旧版的 {user, assistant}
    for item in payload.history:
        if item.get("role") and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
        elif item.get("user"):
            messages.append({"role": "user", "content": item["user"]})
        elif item.get("assistant"):
            messages.append({"role": "assistant", "content": item["assistant"]})

    messages.append({"role": "user", "content": user_message})

    try:
        # 教师对话允许等久一点：1024 tokens DeepSeek 慢起来要 10-20s，
        # 共享 client 默认 12s read 是给雷达 / 预测那类要"快出 fallback"的接口的，
        # 这里单独覆盖到 30s，避免常规对话被截成 timeout
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=AI_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            stream=False,
            timeout=30.0,
        )
        ai_response = response.choices[0].message.content
        return {"response": ai_response}
    except Exception as exc:
        category = classify_ai_error(exc)
        print(f"AI 教师调用失败 [{category}]: {exc}")
        return {
            "response": _FALLBACK_REPLY,
            "fallback": True,
            "error_category": category,
            "error_detail": str(exc)[:200],
        }
