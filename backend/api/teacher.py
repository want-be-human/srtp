from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from openai import OpenAI
import os
from dotenv import load_dotenv

router = APIRouter()

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) 
env_path = os.path.join(parent_dir, '.env')  
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("ERNIE_ACCESS_TOKEN")

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
    print(f"Received payload: {payload.model_dump_json(indent=2)}")
    if not API_KEY:
        raise HTTPException(status_code=500, detail="ERNIE API key not configured")

    client = OpenAI(
    api_key=API_KEY,
    base_url="https://qianfan.baidubce.com/v2"
)

    messages = [{"role": "system", "content": "你是一个专业的焊接技术教学AI助手。你的任务是根据用户提供的检测报告和问题，给出具体、可行的分析和改进建议。"}]
    
    # 如果有上下文（检测结果），将其格式化并加到用户第一条消息前
    user_message = payload.message
    if payload.context and not payload.history: # 只在第一次对话时自动引入上下文
        context_prompt = format_context_for_prompt(payload.context)
        user_message = f"{context_prompt}{payload.message}"

    # 添加历史对话
    for item in payload.history:
        if item.get("user"):
            messages.append({"role": "user", "content": item["user"]})
        if item.get("assistant"):
            messages.append({"role": "assistant", "content": item["assistant"]})
            
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="ernie-3.5-8k",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1024,
            temperature=0.7,
            stream=False
        ) 
        ai_response = response.choices[0].message.content
        return {"response": ai_response}
    except Exception as e:
        print(f"Error calling ERNIE API: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get response from AI teacher. {e}")
