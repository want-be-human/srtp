from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Dict, List, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import subprocess
import sys
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

from database import SessionLocal
import models

# PDF生成任务状态存储（内存缓存）
_pdf_generation_tasks: Dict[str, Dict[str, Any]] = {}

# 线程池用于后台PDF生成
_pdf_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pdf_gen")

# 导入统一的缺陷类型定义
try:
    from defect_types import DEFECT_EN_TO_CN, TRUE_DEFECT_TYPES, get_severity_level, DEFECT_ID_TO_CN
except ImportError:
    # 备用定义
    DEFECT_EN_TO_CN = {
        'Poor Weld': '焊接不良', 'Crack': '裂纹', 'Excess Rebar': '钢筋过剩',
        'Good Weld': '良好焊缝', 'Porosity': '气孔', 'Spatter': '飞溅',
        'Undercut': '咬边', 'Overlap': '焊瘤', 'Incomplete Fusion': '未熔合',
        'Inclusion': '夹渣', 'Distortion': '变形', 'Surface Roughness': '表面粗糙',
        'Excess Penetration': '焊穿', 'Misalignment': '错边', 'Arc Strike': '电弧擦伤',
        'Discoloration': '变色', 'Tool Mark': '工具痕迹'
    }
    TRUE_DEFECT_TYPES = list(DEFECT_EN_TO_CN.values())
    TRUE_DEFECT_TYPES.remove('良好焊缝')
    def get_severity_level(class_id):
        severity_map = {1: '严重', 8: '严重', 9: '严重', 12: '严重', 0: '中等', 4: '中等', 6: '中等', 7: '中等'}
        return severity_map.get(class_id, '轻微')

# 导入AI分析服务
try:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    sys.path.insert(0, backend_dir)
    from ai_analysis import ai_service
except ImportError:
    ai_service = None
    print("AI分析服务导入失败，将使用备用分析")

router = APIRouter()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LessonPlanData(BaseModel):
    """报告数据模型"""
    # 基础统计
    total_students: int
    total_detections: int
    average_score: float

    # 技能分析
    skill_analysis: Dict[str, float]
    skill_trends: Dict[str, List[float]]

    # 缺陷分析
    common_defects: List[Dict[str, Any]]
    defect_trends: Dict[str, int]

    # 学习进度
    student_progress: Dict[str, Any]
    weekly_performance: List[Dict[str, Any]]

    # 教学建议
    teaching_recommendations: List[str]
    focus_areas: List[str]
    next_lesson_plan: Dict[str, Any]

    # 报告元数据
    generated_at: str
    report_period: str

class AILessonAnalysisResponse(BaseModel):
    """AI报告分析响应模型"""
    ai_analysis: Dict[str, Any]
    analysis_time: str
    data_source: str

@router.get("/lesson-plan", response_model=LessonPlanData)
async def get_lesson_plan_data(db: Session = Depends(get_db)):
    """
    获取报告生成所需的综合数据

    批次逻辑：
    - 总数 ≤ 30条：全部计算
    - 总数 > 30条：只取最近30条数据生成报告
    - 批次划分：第1-30条为第1批次，第31-60条为第2批次，以此类推
    """
    try:
        # 获取基础统计数据
        total_detections = db.query(models.WeldingRecord).count()

        if total_detections == 0:
            # 如果没有数据，返回示例数据
            return _generate_sample_lesson_data()

        # 计算平均分数（基于全部数据）
        avg_result = db.query(func.avg(models.WeldingRecord.total_score)).scalar()
        average_score = float(avg_result) if avg_result else 0

        # 业务逻辑：每次检测 = 一个学生
        # 学生总数 = 检测总数
        total_students = total_detections

        # ========== 批次逻辑：取最近30条数据 ==========
        BATCH_SIZE = 30
        recent_records = db.query(models.WeldingRecord).order_by(
            desc(models.WeldingRecord.timestamp)
        ).limit(BATCH_SIZE).all()

        # 反转为时间升序（便于趋势分析）
        recent_records = list(reversed(recent_records))

        # 计算批次信息
        batch_number = (total_detections - 1) // BATCH_SIZE + 1  # 当前批次号
        records_in_batch = min(total_detections, BATCH_SIZE)  # 本批次数据量

        # 技能分析
        skill_analysis = _analyze_skills(recent_records)
        skill_trends = _analyze_skill_trends(recent_records)

        # 缺陷分析
        common_defects = _analyze_defects(recent_records)
        defect_trends = _analyze_defect_trends(recent_records)

        # 学习进度分析
        student_progress = _analyze_student_progress(recent_records)
        weekly_performance = _analyze_weekly_performance(recent_records)

        # 生成教学建议（使用缓存或快速生成，避免AI调用阻塞）
        teaching_recommendations = _get_cached_or_quick_recommendations(skill_analysis, common_defects, average_score)
        focus_areas = _generate_focus_areas(skill_analysis)
        next_lesson_plan = _generate_next_lesson_plan(skill_analysis, common_defects)

        # 计算报告时间范围
        if recent_records:
            first_record_time = recent_records[0].timestamp if recent_records[0].timestamp else datetime.now()
            last_record_time = recent_records[-1].timestamp if recent_records[-1].timestamp else datetime.now()
            report_period = f"{first_record_time.strftime('%Y-%m-%d %H:%M')} 至 {last_record_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            report_period = "暂无数据"

        return LessonPlanData(
            total_students=total_students,
            total_detections=total_detections,
            average_score=round(average_score, 2),
            skill_analysis=skill_analysis,
            skill_trends=skill_trends,
            common_defects=common_defects,
            defect_trends=defect_trends,
            student_progress=student_progress,
            weekly_performance=weekly_performance,
            teaching_recommendations=teaching_recommendations,
            focus_areas=focus_areas,
            next_lesson_plan=next_lesson_plan,
            generated_at=datetime.now().isoformat(),
            report_period=f"第{batch_number}批次 ({records_in_batch}条数据) | {report_period}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告数据失败: {str(e)}")

def _analyze_skills(records: List[models.WeldingRecord]) -> Dict[str, float]:
    """分析技能数据"""
    if not records:
        return {"光滑度": 85.0, "间距": 82.0, "缺陷控制": 88.0}

    smoothness_avg = sum(r.smoothness_score for r in records) / len(records)
    spacing_avg = sum(r.spacing_score for r in records) / len(records)
    defect_avg = sum(r.defect_type_score for r in records) / len(records)

    return {
        "光滑度": round(smoothness_avg, 1),
        "间距": round(spacing_avg, 1),
        "缺陷控制": round(defect_avg, 1)
    }

def _analyze_skill_trends(records: List[models.WeldingRecord]) -> Dict[str, List[float]]:
    """分析技能趋势"""
    if len(records) < 3:
        return {
            "光滑度": [82.0, 85.0, 87.0, 86.0, 88.0],
            "间距": [80.0, 82.0, 85.0, 83.0, 85.0],
            "缺陷控制": [85.0, 87.0, 89.0, 88.0, 90.0]
        }

    # 按时间排序，取最近5个数据点
    sorted_records = sorted(records, key=lambda x: x.timestamp)[-5:]

    return {
        "光滑度": [round(r.smoothness_score, 1) for r in sorted_records],
        "间距": [round(r.spacing_score, 1) for r in sorted_records],
        "缺陷控制": [round(r.defect_type_score, 1) for r in sorted_records]
    }

def _analyze_defects(records: List[models.WeldingRecord]) -> List[Dict[str, Any]]:
    """分析常见缺陷 - 基于实时数据，使用统一的缺陷类型定义"""
    if not records:
        return [
            {"type": "暂无数据", "frequency": 0, "severity": "未知", "improvement": "-"}
        ]

    # 统计缺陷类型
    defect_counts = {}
    for record in records:
        defect_name = record.defect_type_name or "未知"
        # 将英文名称转换为中文
        if defect_name in DEFECT_EN_TO_CN:
            defect_name = DEFECT_EN_TO_CN[defect_name]
        if defect_name not in defect_counts:
            defect_counts[defect_name] = 0
        defect_counts[defect_name] += 1

    # 转换为列表格式，排除良好焊缝
    result = []
    for defect_type, count in sorted(defect_counts.items(), key=lambda x: x[1], reverse=True):
        # 跳过良好焊缝，只统计真正的缺陷
        if defect_type == "良好焊缝":
            continue

        # 根据缺陷类型和频率确定严重程度
        if defect_type in ['裂纹', '未熔合', '焊穿', '夹渣']:
            severity = "严重"
        elif defect_type in ['焊接不良', '气孔', '咬边', '焊瘤']:
            severity = "中等" if count < 10 else "严重"
        else:
            severity = "轻微" if count < 5 else "中等"

        result.append({
            "type": defect_type,
            "frequency": count,
            "severity": severity,
            "improvement": f"{count}次"
        })

    return result if result else [{"type": "无缺陷", "frequency": 0, "severity": "良好", "improvement": "-"}]

def _analyze_defect_trends(records: List[models.WeldingRecord]) -> Dict[str, int]:
    """分析缺陷趋势 - 基于真实数据"""
    if not records:
        return {"本周减少": 0, "上周发现": 0, "改进率": 0}

    # 按时间排序
    sorted_records = sorted(records, key=lambda x: x.timestamp if x.timestamp else datetime.min)

    # 分割为前半部分和后半部分比较
    mid = len(sorted_records) // 2
    first_half = sorted_records[:mid] if mid > 0 else []
    second_half = sorted_records[mid:]

    # 统计两部分的缺陷数量
    first_defects = sum(1 for r in first_half if r.defect_type_name and r.defect_type_name not in ['Good Weld', '良好焊缝', '无缺陷'])
    second_defects = sum(1 for r in second_half if r.defect_type_name and r.defect_type_name not in ['Good Weld', '良好焊缝', '无缺陷'])

    improvement = first_defects - second_defects if first_defects > 0 else 0
    improvement_rate = round((improvement / first_defects) * 100, 0) if first_defects > 0 else 0

    return {
        "本周减少": max(0, improvement),
        "上周发现": first_defects,
        "改进率": improvement_rate
    }

def _analyze_student_progress(records: List[models.WeldingRecord]) -> Dict[str, Any]:
    """分析学生进度 - 基于真实数据"""
    if not records:
        return {"优秀学生": 0, "良好学生": 0, "需要改进": 0, "平均进步率": 0, "最高分": 0, "最低分": 0}

    # 统计学生分布
    scores = [r.total_score for r in records if r.total_score is not None]
    if not scores:
        return {"优秀学生": 0, "良好学生": 0, "需要改进": 0, "平均进步率": 0, "最高分": 0, "最低分": 0}

    avg_score = sum(scores) / len(scores)
    excellent = sum(1 for s in scores if s >= 90)
    good = sum(1 for s in scores if 75 <= s < 90)
    need_improve = sum(1 for s in scores if s < 75)

    # 计算进步率（前后半段对比）
    mid = len(scores) // 2
    if mid > 0:
        first_avg = sum(scores[:mid]) / mid
        second_avg = sum(scores[mid:]) / (len(scores) - mid) if len(scores) > mid else first_avg
        progress_rate = round(second_avg - first_avg, 1)
    else:
        progress_rate = 0

    return {
        "优秀学生": excellent,
        "良好学生": good,
        "需要改进": need_improve,
        "平均进步率": progress_rate,
        "最高分": round(max(scores), 1),
        "最低分": round(min(scores), 1)
    }

def _analyze_weekly_performance(records: List[models.WeldingRecord]) -> List[Dict[str, Any]]:
    """分析每周表现 - 基于真实数据"""
    if not records:
        return []

    from collections import defaultdict

    # 按周分组
    weekly_data = defaultdict(list)
    for r in records:
        if r.timestamp:
            week_num = (datetime.now() - r.timestamp).days // 7
            week_label = f"第{4-week_num}周" if week_num < 4 else "更早"
            weekly_data[week_label].append(r)

    result = []
    for week_label in ["第1周", "第2周", "第3周", "第4周"]:
        week_records = weekly_data.get(week_label, [])
        if week_records:
            scores = [r.total_score for r in week_records if r.total_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0
            result.append({
                "week": week_label,
                "avg_score": round(avg_score, 1),
                "detections": len(week_records),
                "improvement": "-"  # 可以计算周环比
            })
        else:
            result.append({
                "week": week_label,
                "avg_score": 0,
                "detections": 0,
                "improvement": "-"
            })

    return result

# 教学建议缓存（避免频繁调用AI）
_recommendations_cache = {
    "data": None,
    "timestamp": 0,
    "cache_duration": 300  # 缓存5分钟
}

# 通用安全类建议库（约占1/3）
_SAFETY_GENERAL_RECOMMENDATIONS = [
    "严格遵守焊接安全操作规程，确保个人防护装备齐全有效",
    "焊接作业前检查设备状态，确保气路、电路连接正常",
    "保持作业区域整洁有序，及时清理焊接飞溅物和废料",
    "注意焊接烟尘防护，确保通风设备正常运行",
    "定期检查灭火器材，掌握紧急情况处理流程",
    "焊接时佩戴防护眼镜和手套，避免弧光伤害和烫伤",
    "遵守用电安全规范，禁止带电检修焊接设备",
    "高温焊件需设置警示标识，防止烫伤事故发生",
    "合理安排作业时间，避免疲劳作业带来的安全隐患",
    "加强新员工安全培训，建立安全操作考核机制",
    "定期开展安全演练，提高全员安全意识和应急能力",
    "焊接区域禁止存放易燃易爆物品，确保消防安全",
    "关注天气变化，恶劣天气暂停室外焊接作业",
    "建立设备维护档案，定期进行预防性维护保养",
    "焊接完成后检查现场，确认无火源遗留方可离开"
]

def _get_cached_or_quick_recommendations(skill_analysis: Dict[str, float], defects: List[Dict[str, Any]], avg_score: float) -> List[str]:
    """
    基于规则的智能建议生成系统
    根据批次数据（人数、平均分、技能分析、缺陷情况）动态生成个性化建议
    生成至少15条建议，其中约1/3为安全类通用建议
    """
    import time
    import random
    current_time = time.time()

    # 生成建议的哈希键（基于数据特征，数据变化时重新生成）
    data_key = f"{avg_score:.0f}_{skill_analysis.get('光滑度', 0):.0f}_{skill_analysis.get('间距', 0):.0f}_{len(defects)}"

    # 检查缓存是否有效且数据未变化
    if (_recommendations_cache["data"] and
        _recommendations_cache.get("data_key") == data_key and
        current_time - _recommendations_cache["timestamp"] < _recommendations_cache["cache_duration"]):
        return _recommendations_cache["data"]

    recommendations = []

    # ========== 1. 总体评价建议（基于平均分区间）==========
    if avg_score >= 90:
        recommendations.append("优秀批次！整体焊接质量出色，建议保持当前训练强度和方法")
        recommendations.append("可尝试更高难度的焊接任务，如全位置焊接和特殊材料焊接")
        recommendations.append("建议参与技能竞赛或承担示范教学任务，发挥榜样作用")
        recommendations.append("可进行工艺优化探索，总结优秀焊接参数组合")
    elif avg_score >= 80:
        recommendations.append("良好批次，整体质量达标。建议针对薄弱环节进行专项强化")
        recommendations.append("重点关注技能短板，制定个性化提升计划")
        recommendations.append("可适当增加训练难度，稳步提升综合焊接能力")
        recommendations.append("建议进行对比分析，学习优秀批次的操作方法")
    elif avg_score >= 70:
        recommendations.append("合格批次，存在提升空间。建议加强基础技能训练")
        recommendations.append("安排一对一指导，重点纠正操作中的常见错误")
        recommendations.append("增加基础训练课时，夯实焊接基本功")
        recommendations.append("建议采用分段练习法，逐步提高各项技能水平")
    elif avg_score >= 60:
        recommendations.append("需改进批次，建议暂停进度，巩固基础知识")
        recommendations.append("增加模拟练习时间，强化焊接参数选择能力")
        recommendations.append("建议从简单工件开始，逐步建立操作信心")
        recommendations.append("加强理论知识学习，理解焊接原理和工艺要点")
    else:
        recommendations.append("质量预警批次！建议重新学习焊接基础理论和安全规范")
        recommendations.append("安排教师全程跟踪指导，确保安全操作")
        recommendations.append("暂停独立作业，在指导下完成基础训练任务")
        recommendations.append("建立帮扶机制，安排技能优秀者进行一对一辅导")

    # ========== 2. 技能维度建议（基于各技能分数）==========
    smoothness = skill_analysis.get('光滑度', 0)
    spacing = skill_analysis.get('间距', 0)
    defect_control = skill_analysis.get('缺陷控制', 0)

    # 找出最薄弱的技能
    skills = [('光滑度', smoothness), ('间距控制', spacing), ('缺陷控制', defect_control)]
    weak_skills = [s for s in skills if s[1] < 80]
    weak_skills.sort(key=lambda x: x[1])  # 按分数升序

    for skill_name, score in weak_skills[:2]:  # 最多针对2个薄弱技能
        if skill_name == '光滑度':
            if score < 60:
                recommendations.append("光滑度严重不足！重点练习焊枪移动速度和角度控制")
                recommendations.append("建议进行专门的焊缝成型美观度训练")
            elif score < 70:
                recommendations.append("光滑度需提升，注意保持均匀的焊接速度和稳定的手法")
                recommendations.append("可通过观摩优秀焊工操作视频，学习成型技巧")
            else:
                recommendations.append("光滑度有进步空间，建议增加焊缝成型美观度练习")
                recommendations.append("注意焊缝宽度均匀性，避免出现宽窄不一的情况")
        elif skill_name == '间距控制':
            if score < 60:
                recommendations.append("间距控制能力薄弱！加强焊缝宽度均匀性训练")
                recommendations.append("建议使用辅助工具帮助保持焊枪行走轨迹稳定")
            elif score < 70:
                recommendations.append("间距控制需加强，练习保持稳定的焊枪行走轨迹")
                recommendations.append("可通过标记引导线的方式辅助控制焊缝位置")
            else:
                recommendations.append("间距控制可通过规范焊枪角度来进一步改善")
                recommendations.append("注意手眼协调配合，提高轨迹控制精度")
        elif skill_name == '缺陷控制':
            if score < 60:
                recommendations.append("缺陷控制能力急需提升！加强缺陷识别和预防知识学习")
                recommendations.append("建议系统学习各类缺陷的成因、识别和预防方法")
            elif score < 70:
                recommendations.append("缺陷控制需重视，建议回顾各类缺陷的成因和预防方法")
                recommendations.append("可通过缺陷案例分析，加深对预防措施的理解")
            else:
                recommendations.append("缺陷控制可进一步优化，注意焊接参数的正确选择")
                recommendations.append("加强过程自检，及时发现和纠正潜在问题")

    # ========== 3. 缺陷针对性建议 ==========
    if defects:
        defect_types = [d.get('type', '未知') for d in defects[:5]]
        defect_str = '、'.join(defect_types)

        if '气孔' in defect_str:
            recommendations.append("气孔问题需关注，建议检查保护气体流量和焊接速度配合")
            recommendations.append("注意焊前清理，确保母材表面无油污、水汽等污染物")
        if '夹渣' in defect_str:
            recommendations.append("夹渣问题需解决，加强焊缝清洁和层间处理")
            recommendations.append("注意焊接电流选择，确保熔池充分熔化")
        if '裂纹' in defect_str:
            recommendations.append("裂纹问题严重！检查焊接材料预热和层间温度控制")
            recommendations.append("建议调整焊接顺序，减小焊接应力集中")
        if '咬边' in defect_str:
            recommendations.append("咬边问题需纠正，调整焊枪角度和焊接速度")
            recommendations.append("注意电弧位置控制，避免电弧直接作用于母材边缘")
        if '焊瘤' in defect_str or 'Overlap' in defect_str:
            recommendations.append("焊瘤问题需注意，控制熔池温度和送丝速度")
            recommendations.append("建议减小焊接电流或加快焊接速度")
        if '未熔合' in defect_str:
            recommendations.append("未熔合问题需重视，增加电弧观察训练，确保熔合质量")
            recommendations.append("注意层间清理，确保焊道之间良好熔合")
        if '未焊透' in defect_str:
            recommendations.append("未焊透问题需解决，适当增加焊接电流和坡口角度")
            recommendations.append("注意焊接位置调整，确保电弧能够充分熔透根部")

    # ========== 4. 趋势建议（如果有提升空间）==========
    if avg_score >= 75 and len(weak_skills) == 0:
        recommendations.append("各项技能均衡发展，建议进行综合实战训练")
        recommendations.append("可安排复杂工件的焊接任务，提升综合应用能力")
        recommendations.append("鼓励参与工艺改进和质量攻关活动")

    # ========== 5. 添加安全类通用建议（约占1/3，约5条）==========
    # 随机选择5条安全类建议
    safety_recs = random.sample(_SAFETY_GENERAL_RECOMMENDATIONS, min(5, len(_SAFETY_GENERAL_RECOMMENDATIONS)))

    # 将安全建议均匀插入到建议列表中
    total_recs = recommendations[:10]  # 先取前面生成的最多10条针对性建议
    final_recs = []

    # 交替插入：每2条针对性建议后插入1条安全建议
    safety_idx = 0
    for i, rec in enumerate(total_recs):
        final_recs.append(rec)
        if (i + 1) % 2 == 0 and safety_idx < len(safety_recs):
            final_recs.append(safety_recs[safety_idx])
            safety_idx += 1

    # 添加剩余的安全建议
    while safety_idx < len(safety_recs):
        final_recs.append(safety_recs[safety_idx])
        safety_idx += 1

    # 确保至少15条建议
    if len(final_recs) < 15:
        # 添加更多安全类建议
        remaining_safety = [r for r in _SAFETY_GENERAL_RECOMMENDATIONS if r not in final_recs]
        for rec in remaining_safety:
            if len(final_recs) >= 15:
                break
            final_recs.append(rec)

    # 如果还不够，添加一些通用训练建议
    if len(final_recs) < 15:
        general_recs = [
            "定期总结焊接经验，建立个人技术档案",
            "积极参与技术交流，学习先进焊接方法",
            "保持良好的焊接习惯，注重细节操作",
            "建立有效的反馈机制，及时调整训练策略"
        ]
        for rec in general_recs:
            if len(final_recs) >= 15:
                break
            final_recs.append(rec)

    final_recs = final_recs[:18]  # 最多18条建议（约12条针对性+6条安全类）

    # 更新缓存
    _recommendations_cache["data"] = final_recs
    _recommendations_cache["data_key"] = data_key
    _recommendations_cache["timestamp"] = current_time

    return final_recs


async def _generate_teaching_recommendations_with_ai(skill_analysis: Dict[str, float], defects: List[Dict[str, Any]], avg_score: float) -> List[str]:
    """使用AI生成教学建议"""
    # 如果AI服务可用，使用AI生成
    if ai_service:
        try:
            prompt = f"""基于以下焊缝检测数据，生成5-7条教学建议（每条建议20-40字）：

技能分析：
- 光滑度: {skill_analysis.get('光滑度', 0):.1f}分
- 间距控制: {skill_analysis.get('间距', 0):.1f}分
- 缺陷控制: {skill_analysis.get('缺陷控制', 0):.1f}分
- 平均得分: {avg_score:.1f}分

常见缺陷：{', '.join([d['type'] for d in defects[:3]])}

请返回JSON数组格式的建议列表，如：["建议1", "建议2", ...]
只返回JSON数组，不要其他文字。"""

            result = ai_service._call_openai_api([
                {"role": "system", "content": "你是焊接教学专家，负责生成教学建议。只返回JSON数组。"},
                {"role": "user", "content": prompt}
            ], max_tokens=500)

            if result:
                import re
                import json
                json_match = re.search(r'\[.*\]', result, re.DOTALL)
                if json_match:
                    recommendations = json.loads(json_match.group())
                    if isinstance(recommendations, list) and len(recommendations) > 0:
                        return recommendations[:7]
        except Exception as e:
            print(f"AI生成教学建议失败: {e}")

    # 备用：基于规则生成 + 随机选择模拟数据组
    return _generate_teaching_recommendations(skill_analysis, defects)


# 多组模拟教学建议数据（当AI不可用时随机轮换显示）
_MOCK_TEACHING_RECOMMENDATIONS = [
    [
        "加强焊枪握持稳定性训练，重点练习直线焊接轨迹",
        "建议增加焊接速度控制练习，保持匀速操作",
        "针对气孔缺陷，调整保护气体流量参数",
        "安排优秀学生进行现场演示，提升学习效果"
    ],
    [
        "重点关注焊缝成型质量，加强手法规范训练",
        "增加多层多道焊练习，提升综合焊接能力",
        "针对夹渣问题，加强焊缝清洁和层间处理",
        "建议采用视频回放方式分析焊接过程"
    ],
    [
        "强化焊接参数选择训练，理解电流电压关系",
        "增加薄板焊接专项练习，提高精细操作能力",
        "针对咬边缺陷，调整焊枪角度和焊接速度",
        "组织小组竞赛活动，激发学习积极性"
    ],
    [
        "加强焊接基本功训练，注重手眼协调配合",
        "增加仰焊位置练习，提升全位置焊接技能",
        "针对未熔合问题，增加电弧控制和熔池观察训练",
        "建议建立个人学习档案，跟踪进步情况"
    ],
    [
        "重点培养焊接质量意识，建立自检习惯",
        "增加管件焊接练习，拓展焊接应用场景",
        "针对焊瘤问题，调整送丝速度和焊接速度匹配",
        "安排实际工件焊接，增强实战经验"
    ],
    [
        "加强焊接安全操作规范培训，确保安全生产",
        "增加铝合金焊接练习，掌握不同材料特性",
        "针对裂纹问题，控制层间温度和焊接顺序",
        "邀请企业技师进行现场指导交流"
    ]
]

# 多组模拟下节课计划数据
_MOCK_NEXT_LESSON_PLANS = [
    {"主题": "光滑度技能强化训练", "目标": "提升学生光滑度技能至90分以上", "内容": ["光滑度理论知识讲解", "实操演示和指导", "分组练习和讨论", "成果展示和评价"], "重点": "针对光滑度的常见问题进行专项训练", "时长": "90分钟", "评估方式": "现场操作评分 + 理论测试"},
    {"主题": "间距控制专项训练", "目标": "提升学生间距控制技能至90分以上", "内容": ["间距控制要点讲解", "标准间距示范", "反复练习和纠正", "同伴互评环节"], "重点": "掌握焊缝间距的精确控制技术", "时长": "90分钟", "评估方式": "实操考核 + 作品展示"},
    {"主题": "缺陷识别与预防训练", "目标": "提升学生缺陷识别能力，降低缺陷率", "内容": ["常见缺陷案例分析", "缺陷成因讲解", "预防措施演示", "模拟检测练习"], "重点": "学会识别和预防常见焊接缺陷", "时长": "90分钟", "评估方式": "缺陷识别测试 + 实操评分"},
    {"主题": "焊接速度控制训练", "目标": "培养学生稳定的焊接速度控制能力", "内容": ["速度控制原理讲解", "匀速焊接演示", "计时练习环节", "速度调整技巧"], "重点": "掌握不同位置的速度控制技术", "时长": "90分钟", "评估方式": "计时考核 + 焊缝质量评分"},
    {"主题": "全位置焊接综合训练", "目标": "提升学生全位置焊接能力", "内容": ["各位置焊接特点", "平焊立焊横焊练习", "仰焊专项训练", "综合技能考核"], "重点": "掌握不同焊接位置的操作技巧", "时长": "120分钟", "评估方式": "多位置综合考核"},
    {"主题": "焊接质量检测与分析", "目标": "培养学生质量检测和问题分析能力", "内容": ["质量检测标准讲解", "检测工具使用", "缺陷分析方法", "质量改进建议"], "重点": "学会自主检测和分析焊接质量", "时长": "90分钟", "评估方式": "检测报告 + 问题分析"}
]


def _generate_teaching_recommendations(skill_analysis: Dict[str, float], defects: List[Dict[str, Any]]) -> List[str]:
    """生成教学建议（备用方案 - 结合真实数据和随机模拟数据）"""
    import random

    # 先基于真实数据生成针对性建议
    recommendations = []

    # 基于技能分析生成建议
    if skill_analysis.get("光滑度", 0) < 85:
        recommendations.append("加强焊枪握持稳定性训练，重点练习直线焊接")

    if skill_analysis.get("间距", 0) < 85:
        recommendations.append("增加焊接间距控制练习，使用辅助工具帮助学生掌握标准间距")

    if skill_analysis.get("缺陷控制", 0) < 85:
        recommendations.append("强化缺陷识别训练，增加案例分析课程")

    # 基于缺陷分析生成建议
    if defects and len(defects) > 0 and defects[0].get('type') != '暂无数据':
        common_defect = max(defects, key=lambda x: x.get('frequency', 0)) if defects else None
        if common_defect and common_defect.get('type') not in ['无缺陷', '暂无数据']:
            recommendations.append(f"针对最常见缺陷'{common_defect['type']}'制定专项练习计划")

    # 如果基于真实数据的建议不足，从模拟数据中随机补充
    if len(recommendations) < 4:
        mock_recs = random.choice(_MOCK_TEACHING_RECOMMENDATIONS)
        # 随机选择2-3条模拟建议补充
        needed = 4 - len(recommendations)
        additional = random.sample(mock_recs, min(needed, len(mock_recs)))
        recommendations.extend(additional)

    return recommendations[:6]  # 最多返回6条建议

def _generate_focus_areas(skill_analysis: Dict[str, float]) -> List[str]:
    """生成重点关注领域"""
    focus_areas = []

    # 找出得分最低的技能
    min_skill = min(skill_analysis.items(), key=lambda x: x[1])
    focus_areas.append(f"{min_skill[0]}技能提升")

    focus_areas.extend([
        "理论与实践结合",
        "安全操作规范",
        "质量标准理解",
        "工具使用技巧"
    ])

    return focus_areas

def _generate_next_lesson_plan(skill_analysis: Dict[str, float], defects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成下节课计划（结合真实数据和随机模拟数据）"""
    import random

    # 如果有真实技能数据，基于最弱技能生成
    if skill_analysis and any(v > 0 for v in skill_analysis.values()):
        weak_skill = min(skill_analysis.items(), key=lambda x: x[1])
        if weak_skill[1] > 0:  # 确保有真实数据
            return {
                "主题": f"{weak_skill[0]}技能强化训练",
                "目标": f"提升学生{weak_skill[0]}技能至90分以上",
                "内容": [
                    f"{weak_skill[0]}理论知识讲解",
                    "实操演示和指导",
                    "分组练习和讨论",
                    "成果展示和评价"
                ],
                "重点": f"针对{weak_skill[0]}的常见问题进行专项训练",
                "时长": "90分钟",
                "评估方式": "现场操作评分 + 理论测试"
            }

    # 否则随机选择一个模拟计划
    return random.choice(_MOCK_NEXT_LESSON_PLANS)

def _generate_sample_lesson_data() -> LessonPlanData:
    """生成示例报告数据（当没有真实数据时）"""
    return LessonPlanData(
        total_students=50,
        total_detections=0,
        average_score=0.0,
        skill_analysis={"光滑度": 0.0, "间距": 0.0, "缺陷控制": 0.0},
        skill_trends={"光滑度": [], "间距": [], "缺陷控制": []},
        common_defects=[],
        defect_trends={"本周减少": 0, "上周发现": 0, "改进率": 0},
        student_progress={
            "优秀学生": 0, "良好学生": 0, "需要改进": 0,
            "平均进步率": 0.0, "最高分": 0.0, "最低分": 0.0
        },
        weekly_performance=[],
        teaching_recommendations=["暂无数据，请先进行焊接检测以生成教学建议"],
        focus_areas=["基础技能训练"],
        next_lesson_plan={
            "主题": "焊接基础技能入门",
            "目标": "掌握基本焊接操作",
            "内容": ["焊接理论", "工具使用", "安全规范", "基础练习"],
            "重点": "安全操作和基础手法",
            "时长": "90分钟",
            "评估方式": "理论测试 + 实操演示"
        },
        generated_at=datetime.now().isoformat(),
        report_period="暂无数据"
    )


@router.get("/lesson-plan/ai-analysis", response_model=AILessonAnalysisResponse)
async def get_ai_lesson_plan_analysis(db: Session = Depends(get_db)):
    """
    获取AI报告分析
    基于教学数据使用AI进行深度分析和教学建议

    Returns:
        AILessonAnalysisResponse: AI报告分析结果
    """
    try:
        # 首先获取基础报告数据
        lesson_data_response = await get_lesson_plan_data(db)
        lesson_data = lesson_data_response.__dict__

        # 使用AI服务进行分析
        if ai_service:
            ai_result = await ai_service.analyze_lesson_plan_data(lesson_data)
        else:
            # 备用响应
            ai_result = {
                "ai_analysis": {
                    "overall_assessment": "需要配置OPENAI_API_KEY以获取AI教学分析",
                    "student_analysis": {
                        "strengths": ["请配置API密钥以获取AI分析"],
                        "weaknesses": ["请配置API密钥以获取AI分析"],
                        "progress_trend": "需要AI分析"
                    },
                    "focus_skills": ["配置AI后获取分析"],
                    "teaching_recommendations": [
                        "请在环境变量中设置OPENAI_API_KEY",
                        "配置完成后即可获得个性化教学建议",
                        "AI将基于学生实际表现提供专业指导"
                    ],
                    "next_lesson_plan": {
                        "主题": "需要AI分析后确定",
                        "目标": "需要AI分析后确定",
                        "重点": "需要AI分析后确定",
                        "内容": ["配置AI后自动生成"],
                        "时长": "90分钟",
                        "评估方式": "配置AI后自动生成"
                    }
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "FALLBACK"
            }

        return AILessonAnalysisResponse(**ai_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI报告分析失败: {str(e)}")


@router.post("/lesson-plan/ai-analysis-custom")
async def get_custom_ai_lesson_plan_analysis(request_data: Dict[str, Any], db: Session = Depends(get_db)):
    """
    自定义AI报告分析
    基于用户提供的教学数据进行AI分析

    Args:
        request_data: 包含自定义教学数据的请求体

    Returns:
        AILessonAnalysisResponse: AI报告分析结果
    """
    try:
        # 从请求中提取数据，如果没有则使用默认数据
        lesson_data = request_data.get('lesson_data', {})

        if not lesson_data:
            # 如果没有提供数据，获取默认报告数据
            lesson_data_response = await get_lesson_plan_data(db)
            lesson_data = lesson_data_response.__dict__

        # 使用AI服务进行分析
        if ai_service:
            ai_result = await ai_service.analyze_lesson_plan_data(lesson_data)
        else:
            # 备用响应
            ai_result = {
                "ai_analysis": {
                    "overall_assessment": "需要配置OPENAI_API_KEY以获取AI教学分析",
                    "student_analysis": {
                        "strengths": ["请配置API密钥以获取AI分析"],
                        "weaknesses": ["请配置API密钥以获取AI分析"],
                        "progress_trend": "需要AI分析"
                    },
                    "focus_skills": ["配置AI后获取分析"],
                    "teaching_recommendations": [
                        "请在环境变量中设置OPENAI_API_KEY",
                        "配置完成后即可获得个性化教学建议"
                    ],
                    "next_lesson_plan": {
                        "主题": "需要AI分析后确定",
                        "目标": "需要AI分析后确定",
                        "重点": "需要AI分析后确定",
                        "内容": ["配置AI后自动生成"],
                        "时长": "90分钟",
                        "评估方式": "配置AI后自动生成"
                    }
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "FALLBACK"
            }

        return AILessonAnalysisResponse(**ai_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自定义AI报告分析失败: {str(e)}")


@router.get("/lesson-plan/ai-status")
async def get_ai_analysis_status():
    """
    获取AI分析服务状态

    Returns:
        AI服务状态信息
    """
    try:
        # 使用统一配置
        from config import AI_API_KEY, AI_API_BASE_URL, AI_MODEL

        api_key_configured = bool(AI_API_KEY)

        return {
            "ai_service_available": ai_service is not None,
            "api_key_configured": api_key_configured,
            "base_url": AI_API_BASE_URL,
            "model": AI_MODEL,
            "status": "ready" if (ai_service and api_key_configured) else "needs_configuration",
            "message": "AI分析服务已就绪" if (ai_service and api_key_configured) else "需要配置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "ai_service_available": False,
            "api_key_configured": False,
            "status": "error",
            "message": f"AI服务状态检查失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/lesson-plan/pdf-data")
async def get_lesson_plan_pdf_data(db: Session = Depends(get_db)):
    """
    获取PDF生成所需的真实报告数据
    供独立PDF生成器调用

    Returns:
        完整的真实报告数据，用于PDF生成
    """
    try:
        # 获取报告数据
        lesson_data_response = await get_lesson_plan_data(db)
        lesson_data = lesson_data_response.__dict__

        # 转换为PDF生成器需要的格式
        pdf_data = {
            "total_students": lesson_data.get("total_students", 0),
            "total_detections": lesson_data.get("total_detections", 0),
            "average_score": lesson_data.get("average_score", 0.0),
            "skill_analysis": lesson_data.get("skill_analysis", {}),
            "common_defects": lesson_data.get("common_defects", []),
            "student_progress": lesson_data.get("student_progress", {}),
            "teaching_recommendations": lesson_data.get("teaching_recommendations", []),
            "focus_areas": lesson_data.get("focus_areas", []),
            "next_lesson_plan": lesson_data.get("next_lesson_plan", {}),
            "generated_at": datetime.now().isoformat(),
            "report_period": lesson_data.get("report_period", ""),
            "data_source": "real_data" if lesson_data.get("total_detections", 0) > 0 else "demo_data"
        }

        return {
            "status": "success",
            "data": pdf_data,
            "message": f"获取到{'真实' if pdf_data['data_source'] == 'real_data' else '演示'}数据",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"获取PDF数据失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.post("/lesson-plan/generate-pdf")
async def generate_lesson_plan_pdf(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    异步生成报告PDF文件
    立即返回任务ID，前端可轮询查询进度

    Returns:
        dict: 包含任务ID的响应
    """
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())[:8]

    # 初始化任务状态
    _pdf_generation_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "任务已创建，等待开始...",
        "created_at": datetime.now().isoformat(),
        "file_path": None,
        "error": None
    }

    # 添加后台任务
    background_tasks.add_task(_generate_pdf_task, task_id)

    return {
        "status": "started",
        "task_id": task_id,
        "message": "PDF生成任务已启动，请轮询查询进度",
        "poll_url": f"/api/v1/lesson-plan/pdf-status/{task_id}"
    }


def _generate_pdf_task(task_id: str):
    """后台任务：实际执行PDF生成"""
    import glob as glob_module

    try:
        _pdf_generation_tasks[task_id]["status"] = "processing"
        _pdf_generation_tasks[task_id]["message"] = "正在准备数据..."
        _pdf_generation_tasks[task_id]["progress"] = 10

        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        pdf_generator_dir = os.path.join(backend_dir, "services", "pdf_generator")
        pdf_generator_script = os.path.join(pdf_generator_dir, "standalone_pdf_generator.py")

        if not os.path.exists(pdf_generator_script):
            raise Exception(f"PDF生成器未找到: {pdf_generator_script}")

        _pdf_generation_tasks[task_id]["message"] = "正在生成图表和报告..."
        _pdf_generation_tasks[task_id]["progress"] = 30

        # 运行PDF生成器（超时设置为2分钟）
        result = subprocess.run(
            [sys.executable, pdf_generator_script],
            cwd=pdf_generator_dir,
            capture_output=True,
            text=True,
            timeout=120  # 降低到2分钟
        )

        if result.returncode != 0:
            raise Exception(f"PDF生成失败: {result.stderr}")

        _pdf_generation_tasks[task_id]["progress"] = 90
        _pdf_generation_tasks[task_id]["message"] = "正在完成..."

        # 查找最新生成的PDF文件
        pdf_files = glob_module.glob(os.path.join(pdf_generator_dir, "焊接质量分析报告_*.pdf"))
        if not pdf_files:
            raise Exception("PDF文件生成成功但未找到输出文件")

        latest_pdf = max(pdf_files, key=os.path.getctime)

        # 任务完成
        _pdf_generation_tasks[task_id]["status"] = "completed"
        _pdf_generation_tasks[task_id]["progress"] = 100
        _pdf_generation_tasks[task_id]["message"] = "PDF生成完成！"
        _pdf_generation_tasks[task_id]["file_path"] = latest_pdf
        _pdf_generation_tasks[task_id]["completed_at"] = datetime.now().isoformat()

    except subprocess.TimeoutExpired:
        _pdf_generation_tasks[task_id]["status"] = "failed"
        _pdf_generation_tasks[task_id]["error"] = "PDF生成超时（超过2分钟）"
        _pdf_generation_tasks[task_id]["progress"] = 0
    except Exception as e:
        _pdf_generation_tasks[task_id]["status"] = "failed"
        _pdf_generation_tasks[task_id]["error"] = str(e)
        _pdf_generation_tasks[task_id]["progress"] = 0


@router.get("/lesson-plan/pdf-status/{task_id}")
async def get_pdf_status(task_id: str):
    """
    查询PDF生成任务状态

    Args:
        task_id: 任务ID

    Returns:
        dict: 任务状态信息
    """
    if task_id not in _pdf_generation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _pdf_generation_tasks[task_id]
    response = {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"]
    }

    if task["status"] == "completed":
        response["download_url"] = f"/api/v1/lesson-plan/pdf-download/{task_id}"
    elif task["status"] == "failed":
        response["error"] = task.get("error", "未知错误")

    return response


@router.get("/lesson-plan/pdf-download/{task_id}")
async def download_pdf(task_id: str):
    """
    下载生成的PDF文件

    Args:
        task_id: 任务ID

    Returns:
        FileResponse: PDF文件
    """
    if task_id not in _pdf_generation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _pdf_generation_tasks[task_id]

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"任务未完成，当前状态: {task['status']}")

    file_path = task.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF文件不存在")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=os.path.basename(file_path)
    )