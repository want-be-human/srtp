"""
AI分析服务模块 - 使用OpenAI格式API进行智能分析
"""
import json
import re
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# 使用统一配置
from ai_client import get_shared_ai_client
from config import AI_API_BASE_URL, AI_API_KEY, AI_MODEL

logger = logging.getLogger(__name__)

# 远程 LLM 单次调用上限；超过就放弃，回到 fallback 文案。
# DeepSeek 正常 4-8s 一次，但雷达页串在 AI 后面，3s 卡住整页就明显。
# Promise.allSettled 在前端把雷达和 AI 并行了，AI 慢一些不阻塞图表，所以这里
# 收紧到 3s 让"最差体感"始终在 3 秒内出兜底文案。
AI_REQUEST_TIMEOUT_SECONDS = 3.0


def _try_parse_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """先直 json.loads，失败时挑最外层 {...} 再试一次。

    只认 dict，列表 / 字符串 / 数字都判失败——下游 ai_analysis 字段读法要的就是 dict，
    放行非 dict 会让前端读出 undefined 后悄无声息掉到 fallback 文案。
    """
    if not text:
        return None
    parsed: Any
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _build_severity_hint() -> str:
    """把 defect_types.get_severity_level 的分级列成 prompt 友好的多行文本。"""
    try:
        from defect_types import DEFECT_ID_TO_CN, get_severity_level
    except ImportError:
        return ""
    buckets: Dict[str, List[str]] = {"严重": [], "中等": [], "轻微": []}
    for id_, cn_name in DEFECT_ID_TO_CN.items():
        if cn_name == "良好焊缝":
            continue
        buckets.setdefault(get_severity_level(id_), []).append(cn_name)
    lines = ["缺陷严重程度参考（建议优先关注严重 / 中等）："]
    for sev in ("严重", "中等", "轻微"):
        items = buckets.get(sev) or []
        if items:
            lines.append(f"- {sev}：{ '、'.join(items)}")
    return "\n".join(lines)


_SEVERITY_HINT = _build_severity_hint()
_JSON_REPAIR_REMINDER = (
    "上次输出无法解析为 JSON。请只输出一个 JSON 对象本身，不要 markdown 代码块、"
    "不要解释文字、不要任何前后缀。严格按上面给出的字段名和 schema。"
)

class AIAnalysisService:
    """AI分析服务类 - 使用统一配置的API"""

    def __init__(self):
        self.api_key = AI_API_KEY
        self.base_url = AI_API_BASE_URL
        self.model = AI_MODEL
        # 共享 client：teacher.py 也用同一个实例，连接池和超时配置走同一份
        self.client = get_shared_ai_client()

        if self.client:
            print(f"AI分析服务初始化完成，使用模型: {self.model}")
        elif not self.api_key:
            print("警告: 未配置API密钥，AI分析功能将使用备用响应")
        else:
            print("警告: AI客户端初始化失败，AI功能将使用备用响应")

    def _call_openai_api(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        timeout: float = AI_REQUEST_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """调用OpenAI兼容API；timeout 走 OpenAI SDK 的 per-request 超时，触发后立即返回 None。"""
        if not self.client:
            logger.warning("没有可用的API密钥，返回备用响应")
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=False,
                timeout=timeout,
            )
            logger.info("AI API调用成功")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI API调用失败: {e}")
            return None

    async def _call_openai_api_async(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        timeout: float = AI_REQUEST_TIMEOUT_SECONDS,
    ) -> Optional[str]:
        """同步调用挪到线程池，别占住主循环"""
        return await asyncio.to_thread(self._call_openai_api, messages, max_tokens, timeout)

    async def _call_with_json_retry(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
    ) -> Optional[Dict[str, Any]]:
        """跑一次 LLM 调用 + JSON 解析；第一次拿到非法 JSON 时追加 reminder 重试一次。"""
        response = await self._call_openai_api_async(messages, max_tokens=max_tokens)
        parsed = _try_parse_json(response)
        if parsed is not None:
            return parsed
        if not response:
            return None

        logger.warning("AI 第一次输出无法解析为 JSON，追加 schema reminder 重试")
        retry_messages = list(messages) + [
            {"role": "assistant", "content": response},
            {"role": "user", "content": _JSON_REPAIR_REMINDER},
        ]
        retry_response = await self._call_openai_api_async(retry_messages, max_tokens=max_tokens)
        return _try_parse_json(retry_response)

    async def analyze_latest_scores(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """基于最新检测分数进行AI分析"""

        # 构建包含评分标准的提示词
        system_prompt = """你是一位专业的焊接技术指导老师。根据学生的焊接检测分数，提供专业的分析和建议。

评分标准说明：
- 总分范围：0-100分
- 光滑度分数：0-100分 (90+优秀，80-89良好，70-79一般，60-69较差，<60需改进)
- 宽度分数：0-100分 (90+优秀，80-89良好，70-79一般，60-69较差，<60需改进)
- 缺陷检测分数：0-100分 (90+优秀，80-89良好，70-79一般，60-69较差，<60需改进)

请根据这些分数提供：
1. 总体评价
2. 各项技能分析
3. 具体改进建议
4. 下次练习重点

请用简洁专业的语言回复，重点突出实用建议。"""

        user_prompt = f"""学生本次焊接检测结果：
总分：{scores.get('total_score', 0):.1f}分
光滑度：{scores.get('smoothness_score', 0):.1f}分
宽度控制：{scores.get('width_score', 0):.1f}分
缺陷检测：{scores.get('defect_score', 0):.1f}分

请根据这些分数给出专业分析和建议。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        ai_response = await self._call_openai_api_async(messages, max_tokens=800)

        if ai_response:
            return {
                "ai_analysis": {
                    "detailed_analysis": ai_response,
                    "scores_summary": {
                        "总分": f"{scores.get('total_score', 0):.1f}分",
                        "光滑度": f"{scores.get('smoothness_score', 0):.1f}分",
                        "宽度控制": f"{scores.get('width_score', 0):.1f}分",
                        "缺陷检测": f"{scores.get('defect_score', 0):.1f}分"
                    },
                    "analysis_type": "score_based"
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "AI_POWERED"
            }
        else:
            return {
                "ai_analysis": {
                    "detailed_analysis": "请配置OPENAI_API_KEY以获取AI专业分析",
                    "scores_summary": {
                        "总分": f"{scores.get('total_score', 0):.1f}分",
                        "光滑度": f"{scores.get('smoothness_score', 0):.1f}分",
                        "宽度控制": f"{scores.get('width_score', 0):.1f}分",
                        "缺陷检测": f"{scores.get('defect_score', 0):.1f}分"
                    },
                    "analysis_type": "score_based"
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "FALLBACK"
            }

    async def analyze_prediction_data(self, historical_data: List[Dict], current_data: Dict) -> Dict[str, Any]:
        """分析预测数据，生成智能预测结果"""

        # 构建分析prompt
        data_summary = f"""
        历史焊接数据分析：
        - 总检测数据: {len(historical_data)}条
        - 当前平均分: {current_data.get('average_score', 0)}
        - 技能分布: {json.dumps(current_data.get('skill_analysis', {}), ensure_ascii=False)}
        - 常见缺陷: {json.dumps(current_data.get('common_defects', [])[:3], ensure_ascii=False)}

        历史趋势数据:
        {json.dumps([{'date': d.get('timestamp', ''), 'score': d.get('total_score', 0)} for d in historical_data[-10:]], ensure_ascii=False)}
        """

        system_content = (
            "你是一个专业的焊接技术分析师，擅长分析焊接数据并预测学习趋势。"
            "请基于提供的数据进行智能分析，给出专业的预测和建议。"
        )
        if _SEVERITY_HINT:
            system_content = f"{system_content}\n\n{_SEVERITY_HINT}"

        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": f"""请分析以下焊接学习数据，提供智能预测分析：

{data_summary}

请提供以下分析结果（请用JSON格式回复）：
1. 未来5次检测的学习成绩预测趋势
2. 技能发展预测分析
3. 潜在问题识别
4. 改进建议

格式示例：
{{
    "forecast_trend": "整体向好/持平/下降",
    "predicted_scores": [85.2, 86.1, 87.3, 88.0, 88.5],
    "skill_predictions": {{
        "光滑度": "预期提升到XX分",
        "间距": "需要重点关注",
        "缺陷控制": "表现良好"
    }},
    "risk_analysis": ["识别的潜在问题1", "识别的潜在问题2"],
    "improvement_suggestions": ["具体改进建议1", "具体改进建议2", "具体改进建议3"]
}}"""
            }
        ]

        ai_analysis = await self._call_with_json_retry(messages, max_tokens=1500)
        if ai_analysis is None:
            return self._get_fallback_prediction_analysis()
        return {
            "ai_analysis": ai_analysis,
            "analysis_time": datetime.now().isoformat(),
            "data_source": "AI_POWERED",
        }

    async def analyze_lesson_plan_data(self, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析报告数据，生成AI教学建议"""

        data_summary = f"""
        当前教学数据分析：
        - 学生总数: {lesson_data.get('total_students', 0)}人
        - 检测总数: {lesson_data.get('total_detections', 0)}次
        - 平均得分: {lesson_data.get('average_score', 0)}分
        - 技能分析: {json.dumps(lesson_data.get('skill_analysis', {}), ensure_ascii=False)}
        - 常见缺陷: {json.dumps(lesson_data.get('common_defects', []), ensure_ascii=False)}
        - 学生进度: {json.dumps(lesson_data.get('student_progress', {}), ensure_ascii=False)}
        """

        messages = [
            {
                "role": "system",
                "content": "你是一位经验丰富的焊接技术教师和教学专家，擅长根据学生学习数据制定个性化教学计划和给出专业教学建议。"
            },
            {
                "role": "user",
                "content": f"""请基于以下教学数据，为老师提供专业的教学分析和建议：

{data_summary}

请提供以下教学分析（请用JSON格式回复）：
1. 教学情况总体评估
2. 学生学习状态分析
3. 重点需要关注的技能领域
4. 具体的教学改进建议
5. 下次课程的教学重点和计划

格式示例：
{{
    "overall_assessment": "整体教学情况评估",
    "student_analysis": {{
        "strengths": ["学生优势1", "学生优势2"],
        "weaknesses": ["需要改进1", "需要改进2"],
        "progress_trend": "进步趋势分析"
    }},
    "focus_skills": ["重点技能1", "重点技能2", "重点技能3"],
    "teaching_recommendations": [
        "具体教学建议1",
        "具体教学建议2",
        "具体教学建议3",
        "具体教学建议4",
        "具体教学建议5"
    ],
    "next_lesson_plan": {{
        "主题": "下节课主题",
        "目标": "教学目标",
        "重点": "教学重点",
        "内容": ["教学内容1", "教学内容2", "教学内容3"],
        "时长": "课程时长",
        "评估方式": "评估方法"
    }}
}}"""
            }
        ]

        ai_analysis = await self._call_with_json_retry(messages, max_tokens=2000)
        if ai_analysis is None:
            return self._get_fallback_lesson_analysis()
        return {
            "ai_analysis": ai_analysis,
            "analysis_time": datetime.now().isoformat(),
            "data_source": "AI_POWERED",
        }

    def _get_fallback_prediction_analysis(self) -> Dict[str, Any]:
        """预测分析的备用响应"""
        return {
            "ai_analysis": {
                "forecast_trend": "需要配置AI API密钥以获取智能分析",
                "predicted_scores": [85.0, 85.0, 85.0, 85.0, 85.0],
                "skill_predictions": {
                    "光滑度": "需要AI分析",
                    "间距": "需要AI分析",
                    "缺陷控制": "需要AI分析"
                },
                "risk_analysis": ["请配置OPENAI_API_KEY环境变量以启用AI分析"],
                "improvement_suggestions": [
                    "请在后端配置OpenAI API密钥",
                    "配置完成后即可获得个性化AI分析",
                    "AI将基于实际数据提供专业建议"
                ]
            },
            "analysis_time": datetime.now().isoformat(),
            "data_source": "FALLBACK"
        }

    def _get_fallback_lesson_analysis(self) -> Dict[str, Any]:
        """报告分析的备用响应"""
        return {
            "ai_analysis": {
                "overall_assessment": "需要配置AI API密钥以获取智能教学分析",
                "student_analysis": {
                    "strengths": ["请配置API密钥以获取AI分析"],
                    "weaknesses": ["请配置API密钥以获取AI分析"],
                    "progress_trend": "需要AI分析"
                },
                "focus_skills": ["配置AI后获取分析", "配置AI后获取分析"],
                "teaching_recommendations": [
                    "请在后端配置OPENAI_API_KEY环境变量",
                    "配置完成后即可获得个性化教学建议",
                    "AI将基于学生实际表现提供专业指导",
                    "系统将分析学习趋势并给出针对性建议"
                ],
                "next_lesson_plan": {
                    "主题": "需要AI分析后确定",
                    "目标": "需要AI分析后确定",
                    "重点": "需要AI分析后确定",
                    "内容": ["配置AI后自动生成", "配置AI后自动生成"],
                    "时长": "90分钟",
                    "评估方式": "配置AI后自动生成"
                }
            },
            "analysis_time": datetime.now().isoformat(),
            "data_source": "FALLBACK"
        }

# 创建全局实例
ai_service = AIAnalysisService()