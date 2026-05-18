from datetime import datetime, timedelta
import logging
import os
import sys
import json
from typing import Dict, Any, Optional
import time
import threading

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

# 导入数据库相关模块
from database import SessionLocal
import models

# 导入统一的缺陷类型定义
try:
    from defect_types import TRUE_DEFECT_TYPES, ALL_DEFECT_TYPES_CN, DEFECT_EN_TO_CN
except ImportError:
    # 备用定义
    TRUE_DEFECT_TYPES = ['焊接不良', '裂纹', '钢筋过剩', '气孔', '飞溅', '咬边', '焊瘤', '未熔合', '夹渣', '变形', '表面粗糙', '焊穿', '错边', '电弧擦伤', '变色', '工具痕迹']
    ALL_DEFECT_TYPES_CN = TRUE_DEFECT_TYPES + ['良好焊缝']

# 导入AI分析服务
try:
    from ai_analysis import ai_service
except ImportError:
    ai_service = None
    logging.warning("AI分析服务导入失败，将使用备用分析")


# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# ========== 预测缓存机制 ==========
# 缓存配置
PREDICTION_CACHE_THRESHOLD = 1  # 每1次检测就重新计算预测（实时更新）
CACHE_TTL_SECONDS = 60  # 缓存有效期60秒

# 全局缓存
_prediction_cache = {
    "last_result": None,
    "last_record_count": 0,
    "last_calculation_time": 0,
    "detection_count_since_update": 0,
    "lock": threading.Lock()
}

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_detection_data_from_db(db, limit: int = 100) -> list:
    """
    从数据库获取检测数据（替代全局变量）

    Args:
        db: 数据库会话
        limit: 最大记录数

    Returns:
        list: 检测数据列表
    """
    records = db.query(models.WeldingRecord).order_by(
        models.WeldingRecord.timestamp.desc()
    ).limit(limit).all()

    data = []
    for record in reversed(records):  # 反转为时间升序
        data.append({
            'id': record.id,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None,
            'total_score': record.total_score or 0,
            'smoothness_score': record.smoothness_score or 0,
            'width_score': record.spacing_score or 0,  # 映射字段名
            'defect_score': record.defect_type_score or 0,
            'defect_type_name': record.defect_type_name or '未知',  # 添加缺陷类型名称
            'student_id': record.student_id,
            'batch_id': record.batch_id,
            'data_source': 'DATABASE'
        })
    return data


def _generate_demo_data(days: int = 15) -> list:
    """
    生成演示数据（当数据库无数据时使用）

    Args:
        days: 生成数据的天数

    Returns:
        list: 演示数据列表
    """
    import random
    base_date = datetime.now() - timedelta(days=days)
    data = []

    for i in range(days):
        progress_factor = min(1.0, i / 10.0)
        base_score = 75 + progress_factor * 15 + random.uniform(-5, 5)

        data.append({
            'timestamp': (base_date + timedelta(days=i)).isoformat(),
            'total_score': max(60, min(95, base_score)),
            'smoothness_score': max(60, min(95, base_score + random.uniform(-3, 3))),
            'width_score': max(60, min(95, base_score + random.uniform(-3, 3))),
            'defect_score': max(60, min(95, base_score + random.uniform(-3, 3))),
            'data_source': 'DEMO'
        })
    return data

# Pydantic 模型定义
class PredictionResponse(BaseModel):
    """预测接口返回模型"""
    history: Dict[str, float]
    forecast: Dict[str, float]
    skill_stats: Dict[str, float]
    defect_stats: Dict[str, float]
    total_detections: int  # 总检测次数（数据库记录总数）

class AIAnalysisResponse(BaseModel):
    """AI分析响应模型"""
    ai_analysis: Dict[str, Any]
    analysis_time: str
    data_source: str

class PredictionStats(BaseModel):
    """预测统计信息模型"""
    total_data_points: int
    forecast_points: int
    prediction_accuracy: float
    last_updated: str

class YOLODetectionData(BaseModel):
    """YOLO检测数据模型"""
    total_score: float
    smoothness_score: Optional[float] = None
    smoothness: Optional[float] = None
    width_score: Optional[float] = None
    width: Optional[float] = None
    defect_score: Optional[float] = None
    defect_type: Optional[float] = None
    timestamp: Optional[str] = None
    actual_width: Optional[float] = None
    defect_type_name: Optional[str] = "无缺陷"

@router.get("/predict", response_model=PredictionResponse)
async def get_prediction(db: Session = Depends(get_db)):
    """
    获取焊缝质量预测数据和可视化图表

    调用顺序：
    1. 获取真实检测数据 - 使用前端上传视频后的检测结果
    2. predict_future_scores() - 预测未来5次检测得分
    3. 生成技能和缺陷统计 - 基于真实检测结果统计

    Returns:
        PredictionResponse: 包含历史数据、预测数据和统计信息

    Note:
        需要先上传视频进行检测，系统才有数据进行预测分析

    缓存策略:
        - 每10次新检测才重新计算预测
        - 缓存有效期60秒
        - 返回缓存数据时会在日志中标注
    """
    try:
        # ========== 缓存检查 ==========
        current_record_count = db.query(models.WeldingRecord).count()
        current_time = time.time()

        with _prediction_cache["lock"]:
            # 检查是否需要重新计算
            need_recalculate = False
            cache_reason = ""

            # 1. 如果没有缓存结果，需要计算
            if _prediction_cache["last_result"] is None:
                need_recalculate = True
                cache_reason = "无缓存"

            # 2. 如果检测记录数变化超过阈值，需要重新计算
            new_detections = current_record_count - _prediction_cache["last_record_count"]
            if new_detections >= PREDICTION_CACHE_THRESHOLD:
                need_recalculate = True
                cache_reason = f"新增{new_detections}条记录超过阈值{PREDICTION_CACHE_THRESHOLD}"

            # 3. 如果缓存过期，需要重新计算
            if current_time - _prediction_cache["last_calculation_time"] > CACHE_TTL_SECONDS * 10:
                need_recalculate = True
                cache_reason = "缓存过期"

            # 返回缓存结果（不满阈值时）
            if not need_recalculate and _prediction_cache["last_result"]:
                # 即使使用缓存，也要重新获取最新的检测数据来更新history
                # 这样确保 history 数据点数量和 total_detections 一致
                detection_data = _get_detection_data_from_db(db, limit=100)

                if detection_data:
                    recent_data = detection_data[-30:] if len(detection_data) > 30 else detection_data

                    # 重新生成 history 数据（处理时间戳重复的情况）
                    new_history = {}
                    for i, data_point in enumerate(recent_data):
                        timestamp = data_point.get('timestamp', datetime.now().isoformat())
                        # 如果时间戳已存在，添加序号后缀避免覆盖
                        original_timestamp = timestamp
                        dup_counter = 1
                        while timestamp in new_history:
                            # 在原始时间戳基础上添加递增的秒数
                            try:
                                ts_dt = datetime.fromisoformat(original_timestamp) + timedelta(seconds=dup_counter)
                                timestamp = ts_dt.isoformat()
                            except Exception:
                                timestamp = f"{original_timestamp}_{dup_counter}"
                            dup_counter += 1
                        score = float(data_point.get('total_score', 85))
                        new_history[timestamp] = round(score, 2)

                    cached_result = _prediction_cache["last_result"]

                    # 创建新的响应对象（Pydantic模型不可变）
                    response = PredictionResponse(
                        history=new_history,
                        forecast=cached_result.forecast,
                        skill_stats=cached_result.skill_stats,
                        defect_stats=cached_result.defect_stats,
                        total_detections=current_record_count
                    )

                    logger.info(f"使用缓存结果，已更新history为最新数据 ({len(new_history)}条记录, total_detections={current_record_count})")
                    return response

                # 如果无法获取数据，使用旧的缓存逻辑
                cached_result = _prediction_cache["last_result"]
                response = PredictionResponse(
                    history=cached_result.history,
                    forecast=cached_result.forecast,
                    skill_stats=cached_result.skill_stats,
                    defect_stats=cached_result.defect_stats,
                    total_detections=current_record_count
                )
                logger.info(f"使用缓存结果 (无法获取最新数据)")
                return response

        logger.info(f"开始执行预测流程... (原因: {cache_reason})")

        # 动态导入模块（如果之前导入失败）
        import importlib
        try:
            data_gen = importlib.import_module('data_generator')
            prediction_mod = importlib.import_module('prediction')

            generate_dataset = data_gen.generate_dataset
            predict_future_scores = prediction_mod.predict_future_scores
        except ImportError as e:
            logger.warning(f"导入预测模块失败: {e}, 使用备用简化预测功能")
            # 使用简化的预测功能
            def simple_predict_future_scores(historical_data, days=5):
                import numpy as np
                # 注意：datetime 和 timedelta 已在文件顶部导入，不要在这里重复导入

                # 简化的预测算法：基于历史数据的线性趋势
                scores = historical_data['score'].values if 'score' in historical_data else []
                if len(scores) == 0:
                    scores = [85.0] * 5  # 默认分数

                # 计算简单的趋势
                if len(scores) > 1:
                    trend = (scores[-1] - scores[0]) / len(scores)
                else:
                    trend = 0

                # 生成预测数据
                last_score = scores[-1] if len(scores) > 0 else 85.0
                forecast_scores = []
                for i in range(days):
                    predicted_score = max(60, min(95, last_score + trend * (i + 1) + np.random.normal(0, 2)))
                    forecast_scores.append(predicted_score)

                # 生成时间序列
                base_time = datetime.now()
                history = {}
                forecast = {}

                # 历史数据
                for i, score in enumerate(scores):
                    time_key = (base_time - timedelta(days=len(scores)-i)).strftime("%Y-%m-%d %H:%M:%S")
                    history[time_key] = round(score, 2)

                # 预测数据
                for i, score in enumerate(forecast_scores):
                    time_key = (base_time + timedelta(days=i+1)).strftime("%Y-%m-%d %H:%M:%S")
                    forecast[time_key] = round(score, 2)

                return {
                    'history': history,
                    'forecast': forecast
                }

            predict_future_scores = simple_predict_future_scores

        # 步骤1: 从数据库加载历史数据
        logger.info("步骤1: 从数据库加载历史数据...")

        # 使用辅助函数从数据库获取数据（替代全局变量）
        detection_data = _get_detection_data_from_db(db, limit=100)

        # 如果数据库无数据，使用演示数据
        if not detection_data:
            logger.info("当前系统暂无检测数据，使用示例数据进行演示")
            detection_data = _generate_demo_data(days=15)
        else:
            logger.info(f"从数据库加载了 {len(detection_data)} 条历史记录")

        # 将存储的列表数据转换为DataFrame格式
        import pandas as pd
        # datetime 和 timedelta 已在文件顶部导入

        # 使用最近30条数据进行预测（如果数据不足30条，则使用全部数据）
        recent_data = detection_data[-30:] if len(detection_data) > 30 else detection_data

        data_rows = []
        for i, data_point in enumerate(recent_data):
            # 转换数据格式以匹配预测算法期望
            row = {
                't': pd.to_datetime(data_point.get('timestamp', datetime.now() - timedelta(days=len(recent_data)-i))),
                'x': float(data_point.get('smoothness_score', data_point.get('total_score', 85))),  # 光滑度分数
                'y': float(data_point.get('width_score', data_point.get('total_score', 85))),        # 宽度分数
                'z': float(data_point.get('defect_score', data_point.get('total_score', 85))),       # 缺陷分数
                'score': float(data_point.get('total_score', 85))  # 总分
            }
            data_rows.append(row)

        historical_data = pd.DataFrame(data_rows)
        logger.info(f"使用最近 {len(historical_data)} 条数据进行预测（共 {len(detection_data)} 条历史数据）")

        # 步骤2: 预测未来得分
        logger.info("步骤2: 执行预测算法...")
        prediction_result = predict_future_scores(historical_data, days=5)
        logger.info(f"预测完成，历史数据点: {len(prediction_result['history'])}, 预测数据点: {len(prediction_result['forecast'])}")

        # 步骤3: 生成技能统计数据
        logger.info("步骤3: 生成技能统计数据...")
        # 基于历史数据计算平均技能指标
        import numpy as np

        if detection_data:
            # 使用最近30条数据（或全部数据如果不足30条）计算技能统计
            recent_data = detection_data[-30:] if len(detection_data) > 30 else detection_data

            smoothness_scores = [data.get('smoothness_score', data.get('total_score', 85)) for data in recent_data]
            width_scores = [data.get('width_score', data.get('total_score', 85)) for data in recent_data]
            defect_scores = [data.get('defect_score', data.get('total_score', 85)) for data in recent_data]
            total_scores = [data.get('total_score', 85) for data in recent_data]

            skill_stats = {
                "光滑度": round(np.mean(smoothness_scores), 2),
                "间距": round(np.mean(width_scores), 2),
                "缺陷控制": round(np.mean(defect_scores), 2),
                "整体技能": round(np.mean(total_scores), 2)
            }
            logger.info(f"使用最近 {len(recent_data)} 条数据计算技能统计（共 {len(detection_data)} 条历史数据）")
        else:
            # 当前系统暂无真实检测数据，请先进行视频检测
            skill_stats = {
                "光滑度": 0,
                "间距": 0,
                "缺陷控制": 0,
                "整体技能": 0
            }
            logger.info("无真实数据，返回空技能统计")

        # 步骤4: 生成缺陷统计数据
        logger.info("步骤4: 生成缺陷统计数据...")

        if detection_data:
            # 使用最近30条数据（或全部数据如果不足30条）统计缺陷类型
            recent_data = detection_data[-30:] if len(detection_data) > 30 else detection_data

            # 初始化缺陷计数（使用统一的缺陷类型定义）
            defect_counts = {defect_type: 0 for defect_type in TRUE_DEFECT_TYPES}
            defect_counts["良好焊缝"] = 0
            defect_counts["未知"] = 0
            total_detections = len(recent_data)

            for data in recent_data:
                # 使用数据库中的defect_type_name字段
                defect_type = data.get('defect_type_name', '未知')
                # 尝试将英文名称转换为中文
                if defect_type in DEFECT_EN_TO_CN:
                    defect_type = DEFECT_EN_TO_CN[defect_type]
                if defect_type in defect_counts:
                    defect_counts[defect_type] += 1
                else:
                    defect_counts["未知"] += 1

            # 转换为百分比（排除良好焊缝和未知，只统计实际缺陷）
            actual_defects = {k: v for k, v in defect_counts.items() if k not in ["良好焊缝", "未知"]}
            total_defects = sum(actual_defects.values())

            if total_defects > 0:
                defect_stats = {
                    key: round((count / total_defects) * 100, 2)
                    for key, count in actual_defects.items() if count > 0  # 只显示有数据的缺陷类型
                }
            else:
                # 如果没有实际缺陷，显示无缺陷比例
                defect_stats = {
                    "无缺陷": round((defect_counts.get("良好焊缝", 0) / total_detections) * 100, 2) if total_detections > 0 else 0
                }

            logger.info(f"基于最近 {len(recent_data)} 条数据统计缺陷分布: {defect_stats}")
        else:
            # 当前系统暂无真实检测数据，请先进行视频检测
            defect_stats = {defect_type: 0 for defect_type in TRUE_DEFECT_TYPES[:6]}  # 返回前6种缺陷类型的空统计
            logger.info("无真实数据，返回空缺陷统计")

        # 构建返回结果
        response = PredictionResponse(
            history=prediction_result['history'],
            forecast=prediction_result['forecast'],
            skill_stats=skill_stats,
            defect_stats=defect_stats,
            total_detections=current_record_count  # 使用数据库总记录数
        )

        # ========== 更新缓存 ==========
        with _prediction_cache["lock"]:
            _prediction_cache["last_result"] = response
            _prediction_cache["last_record_count"] = current_record_count
            _prediction_cache["last_calculation_time"] = current_time

        logger.info("预测流程执行完成，结果已缓存")
        return response
        
    except Exception as e:
        logger.error(f"预测流程执行失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预测服务异常: {str(e)}")


@router.get("/predict/stats", response_model=PredictionStats)
async def get_prediction_stats():
    """
    获取预测系统统计信息
    
    Returns:
        PredictionStats: 预测系统的统计信息
    """
    try:
        # 生成一些示例统计数据
        # 在实际应用中，这些数据应该从数据库或缓存中获取
        # datetime 已在文件顶部导入

        stats = PredictionStats(
            total_data_points=30,
            forecast_points=5,
            prediction_accuracy=85.7,  # 示例准确率
            last_updated=datetime.now().isoformat()
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"统计服务异常: {str(e)}")


@router.post("/predict/custom")
async def custom_prediction(
    data: Dict[str, Any],
    days: int = 5
):
    """
    自定义数据预测接口

    Args:
        data: 自定义的历史数据
        days: 预测次数，默认5次
        
    Returns:
        自定义预测结果
    """
    try:
        logger.info(f"执行自定义预测，预测次数: {days}")
        
        # 动态导入模块
        import importlib
        try:
            data_gen = importlib.import_module('data_generator')
            prediction_mod = importlib.import_module('prediction')
            
            generate_dataset = data_gen.generate_dataset
            predict_future_scores = prediction_mod.predict_future_scores
        except ImportError as e:
            logger.error(f"导入模块失败: {e}")
            raise HTTPException(status_code=500, detail=f"服务器配置错误: {e}")

        # 使用辅助函数从数据库获取数据
        detection_data = _get_detection_data_from_db(db, limit=100)
        if not detection_data:
            raise HTTPException(status_code=400, detail="当前系统暂无检测数据，请先上传视频进行检测后再进行预测分析")

        # 将存储的检测数据转换为DataFrame格式
        import pandas as pd
        # datetime 和 timedelta 已在文件顶部导入

        data_rows = []
        for i, data_point in enumerate(detection_data):
            row = {
                't': pd.to_datetime(data_point.get('timestamp', datetime.now() - timedelta(days=len(detection_data)-i))),
                'x': float(data_point.get('smoothness_score', data_point.get('total_score', 85))),
                'y': float(data_point.get('width_score', data_point.get('total_score', 85))),
                'z': float(data_point.get('defect_score', data_point.get('total_score', 85))),
                'score': float(data_point.get('total_score', 85))
            }
            data_rows.append(row)

        base_data = pd.DataFrame(data_rows)
        
        # 如果用户提供了数据，可以在这里处理合并逻辑
        # 例如：将实时检测数据添加到历史数据中
        
        # 执行预测
        prediction_result = predict_future_scores(base_data, days=days)
        
        # 只返回数值数据，不生成图表（减少响应时间）
        return {
            "history": prediction_result['history'],
            "forecast": prediction_result['forecast'],
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"自定义预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"自定义预测异常: {str(e)}")


@router.get("/predict/charts-only")
async def get_charts_only():
    """
    仅获取图表数据的接口（用于前端图表更新）
    
    Returns:
        仅包含图表base64字符串的响应
    """
    try:
        logger.info("生成仅图表数据...")
        
        # 动态导入模块
        import importlib
        try:
            data_gen = importlib.import_module('data_generator')
            prediction_mod = importlib.import_module('prediction')
            line_chart_mod = importlib.import_module('charts.line_chart')
            radar_chart_mod = importlib.import_module('charts.radar_chart')
            
            generate_dataset = data_gen.generate_dataset
            predict_future_scores = prediction_mod.predict_future_scores
            plot_prediction_chart = line_chart_mod.plot_prediction_chart
            plot_defect_radar = radar_chart_mod.plot_defect_radar
            plot_skill_radar = radar_chart_mod.plot_skill_radar
            generate_sample_data = radar_chart_mod.generate_sample_data
        except ImportError as e:
            logger.error(f"导入模块失败: {e}")
            raise HTTPException(status_code=500, detail=f"服务器配置错误: {e}")

        # 使用辅助函数从数据库获取数据
        detection_data = _get_detection_data_from_db(db, limit=100)
        if not detection_data:
            raise HTTPException(status_code=400, detail="当前系统暂无检测数据，请先上传视频进行检测后再生成图表")

        # 转换真实数据格式
        import pandas as pd
        # datetime 和 timedelta 已在文件顶部导入

        data_rows = []
        for i, data_point in enumerate(detection_data):
            row = {
                't': pd.to_datetime(data_point.get('timestamp', datetime.now() - timedelta(days=len(detection_data)-i))),
                'x': float(data_point.get('smoothness_score', data_point.get('total_score', 85))),
                'y': float(data_point.get('width_score', data_point.get('total_score', 85))),
                'z': float(data_point.get('defect_score', data_point.get('total_score', 85))),
                'score': float(data_point.get('total_score', 85))
            }
            data_rows.append(row)

        historical_data = pd.DataFrame(data_rows)
        prediction_result = predict_future_scores(historical_data, days=5)
        
        # 生成图表
        line_chart_base64 = plot_prediction_chart(
            prediction_result['history'], 
            prediction_result['forecast']
        )
        
        defect_data, skill_data = generate_sample_data()
        defect_radar_base64 = plot_defect_radar(defect_data)
        skill_radar_base64 = plot_skill_radar(skill_data)
        
        return {
            "line_chart": line_chart_base64,
            "defect_radar": defect_radar_base64,
            "skill_radar": skill_radar_base64,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"生成图表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"图表生成异常: {str(e)}")


@router.get("/predict/health")
async def health_check():
    """
    预测服务健康检查
    
    Returns:
        服务状态信息
    """
    try:
        # 执行简单的功能测试
        import importlib
        try:
            data_gen = importlib.import_module('data_generator')
            prediction_mod = importlib.import_module('prediction')

            generate_dataset = data_gen.generate_dataset
            predict_future_scores = prediction_mod.predict_future_scores
        except ImportError as e:
            raise Exception(f"模块导入失败: {e}")

        # 使用辅助函数从数据库获取数据
        detection_data = _get_detection_data_from_db(db, limit=100)
        if detection_data:
            return {
                "status": "healthy",
                "message": "预测服务运行正常，已有真实检测数据",
                "real_data_points": len(detection_data),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "ready",
                "message": "预测服务已就绪，等待检测数据",
                "real_data_points": 0,
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"预测服务异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/predict/ai-analysis", response_model=AIAnalysisResponse)
async def get_ai_prediction_analysis():
    """
    获取AI智能预测分析
    基于历史数据使用AI进行深度分析和预测

    Returns:
        AIAnalysisResponse: AI分析结果
    """
    try:
        logger.info("开始AI预测分析...")

        # 使用辅助函数从数据库获取数据
        db = next(get_db())
        detection_data = _get_detection_data_from_db(db, limit=100)
        if not detection_data:
            raise HTTPException(status_code=400, detail="当前系统暂无检测数据，请先上传视频进行检测后再进行AI分析")

        # 获取历史数据
        historical_data = detection_data

        # 转换DataFrame为字典列表
        import pandas as pd
        import numpy as np

        if isinstance(historical_data, pd.DataFrame):
            # 转换为字典列表
            historical_data = historical_data.to_dict('records')

        # 构建当前数据概要
        # 处理历史数据格式
        total_scores = []
        smoothness_scores = []
        width_scores = []
        defect_scores = []

        for d in historical_data:
            if isinstance(d, dict):
                total_scores.append(d.get('total_score', 85))
                smoothness_scores.append(d.get('smoothness_score', 85))
                width_scores.append(d.get('width_score', 82))
                defect_scores.append(d.get('defect_score', 88))
            else:
                # 如果是其他格式，使用默认值
                total_scores.append(85)
                smoothness_scores.append(85)
                width_scores.append(82)
                defect_scores.append(88)

        current_data = {
            "average_score": round(np.mean(total_scores), 2),
            "skill_analysis": {
                "光滑度": round(np.mean(smoothness_scores), 1),
                "间距": round(np.mean(width_scores), 1),
                "缺陷控制": round(np.mean(defect_scores), 1)
            },
            "common_defects": [
                {"type": "气孔", "frequency": 15},
                {"type": "夹渣", "frequency": 8},
                {"type": "咬边", "frequency": 6}
            ]
        }

        # 使用AI服务进行分析
        if ai_service:
            ai_result = await ai_service.analyze_prediction_data(historical_data, current_data)
        else:
            # 备用响应
            ai_result = {
                "ai_analysis": {
                    "forecast_trend": "需要配置OPENAI_API_KEY以获取AI分析",
                    "predicted_scores": [85.0, 85.0, 85.0, 85.0, 85.0],
                    "skill_predictions": {
                        "光滑度": "需要AI分析",
                        "间距": "需要AI分析",
                        "缺陷控制": "需要AI分析"
                    },
                    "risk_analysis": ["请配置OpenAI API密钥以启用AI分析"],
                    "improvement_suggestions": [
                        "请在环境变量中设置OPENAI_API_KEY",
                        "配置完成后即可获得个性化AI分析"
                    ]
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "FALLBACK"
            }

        logger.info("AI预测分析完成")
        return AIAnalysisResponse(**ai_result)

    except Exception as e:
        logger.error(f"AI预测分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI分析服务异常: {str(e)}")


@router.post("/predict/ai-analysis-scores")
async def analyze_scores_with_ai(scores_data: Dict[str, float]):
    """
    基于检测分数进行AI分析 - 简化版本
    只需要传递最后一次检测的分数数据

    参数格式:
    {
        "total_score": 85.5,
        "smoothness_score": 88.0,
        "width_score": 82.0,
        "defect_score": 87.5
    }
    """
    try:
        logger.info("开始基于检测分数的AI分析...")

        # 使用AI服务进行分析
        if ai_service:
            ai_result = await ai_service.analyze_latest_scores(scores_data)
        else:
            # 备用响应
            ai_result = {
                "ai_analysis": {
                    "detailed_analysis": "需要配置OPENAI_API_KEY以获取AI分析",
                    "scores_summary": {
                        "总分": f"{scores_data.get('total_score', 0):.1f}分",
                        "光滑度": f"{scores_data.get('smoothness_score', 0):.1f}分",
                        "宽度控制": f"{scores_data.get('width_score', 0):.1f}分",
                        "缺陷检测": f"{scores_data.get('defect_score', 0):.1f}分"
                    },
                    "analysis_type": "score_based"
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "FALLBACK"
            }

        logger.info("基于分数的AI分析完成")
        return ai_result

    except Exception as e:
        logger.error(f"分数AI分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI分析服务异常: {str(e)}")


@router.post("/predict/ai-analysis-custom")
async def get_custom_ai_prediction_analysis(request_data: Dict[str, Any]):
    """
    自定义AI预测分析
    基于用户提供的数据进行AI分析

    Args:
        request_data: 包含自定义数据的请求体

    Returns:
        AIAnalysisResponse: AI分析结果
    """
    try:
        logger.info("开始自定义AI预测分析...")

        # 从请求中提取数据
        historical_data = request_data.get('historical_data', [])
        current_data = request_data.get('current_data', {})

        # 记录接收的数据（不再使用内存缓存，数据通过 yolo_realtime.py 的 save_score API 保存到数据库）
        if historical_data:
            logger.info(f"接收到 {len(historical_data)} 条检测数据进行分析")

        # 如果没有提供数据，要求先进行检测
        if not historical_data:
            raise HTTPException(status_code=400, detail="请先上传视频进行检测，或在请求中提供检测数据")

        # 使用AI服务进行分析
        if ai_service:
            ai_result = await ai_service.analyze_prediction_data(historical_data, current_data)
        else:
            # 备用响应
            ai_result = {
                "ai_analysis": {
                    "forecast_trend": "需要配置OPENAI_API_KEY以获取AI分析",
                    "predicted_scores": [85.0, 85.0, 85.0, 85.0, 85.0],
                    "skill_predictions": {
                        "光滑度": "需要AI分析",
                        "间距": "需要AI分析",
                        "缺陷控制": "需要AI分析"
                    },
                    "risk_analysis": ["请配置OpenAI API密钥以启用AI分析"],
                    "improvement_suggestions": [
                        "请在环境变量中设置OPENAI_API_KEY",
                        "配置完成后即可获得个性化AI分析"
                    ]
                },
                "analysis_time": datetime.now().isoformat(),
                "data_source": "FALLBACK"
            }

        logger.info("自定义AI预测分析完成")
        return AIAnalysisResponse(**ai_result)

    except Exception as e:
        logger.error(f"自定义AI预测分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"自定义AI分析服务异常: {str(e)}")


@router.post("/predict/yolo-data")
async def receive_yolo_detection_data(yolo_data: YOLODetectionData, db: Session = Depends(get_db)):
    """
    接收YOLO实时检测数据并存储到预测系统（持久化到数据库）

    Args:
        yolo_data: YOLO检测数据
        格式: {
            "total_score": 85.6,
            "smoothness_score": 88.2,
            "width_score": 82.4,
            "defect_score": 86.8,
            "timestamp": "2025-01-15T10:30:00Z",
            "actual_width": 5.5,
            "defect_type_name": "无缺陷"
        }

    Returns:
        确认信息和预测更新
    """
    try:
        logger.info("收到YOLO检测数据...")

        # 转换YOLO数据格式到预测系统格式
        # 兼容两种格式：带_score后缀和不带后缀的
        detection_data = {
            'total_score': yolo_data.total_score,
            'smoothness_score': yolo_data.smoothness_score or yolo_data.smoothness or 0,
            'width_score': yolo_data.width_score or yolo_data.width or 0,
            'defect_score': yolo_data.defect_score or yolo_data.defect_type or 0,
            'timestamp': yolo_data.timestamp or datetime.now().isoformat(),
            'detection_type': 'yolo_realtime',
            'actual_width': yolo_data.actual_width or 0,
            'defect_type_name': yolo_data.defect_type_name or '无缺陷',
            'received_at': datetime.now().isoformat()
        }

        # 保存到数据库（不再使用内存缓存，完全依赖数据库）
        db_record = models.WeldingRecord(
            smoothness_score=detection_data['smoothness_score'],
            spacing_score=detection_data['width_score'],
            defect_type_score=detection_data['defect_score'],
            total_score=detection_data['total_score']
        )
        db.add(db_record)
        db.commit()
        db.refresh(db_record)

        logger.info(f"YOLO数据已存储到数据库，记录ID: {db_record.id}")

        return {
            "status": "success",
            "message": "YOLO检测数据已接收并保存到数据库",
            "database_id": db_record.id,
            "prediction_updated": True,
            "latest_prediction": {
                "total_score": detection_data['total_score'],
                "timestamp": detection_data['timestamp']
            }
        }

    except Exception as e:
        logger.error(f"接收YOLO数据失败: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"YOLO数据接收失败: {str(e)}")


# ========== AI雷达图数据端点 ==========
class RadarDataResponse(BaseModel):
    """雷达图数据模型"""
    defect_radar: Dict[str, float]
    skill_radar: Dict[str, float]
    ai_summary: str
    analysis_time: str
    data_source: str


# 预设的模拟数据组（5分钟刷新一次，数据呈增长趋势）
# 数据排列：夹渣最常见 > 气孔 > 其他差不多
_MOCK_RADAR_DATA = [
    # 初始数据
    {
        "defect_radar": {"夹渣": 45, "气孔": 35, "焊瘤": 25, "咬边": 22, "未熔合": 18, "裂纹": 12},
        "skill_radar": {"光滑度": 72, "间距控制": 75, "缺陷控制": 70, "焊缝宽度": 68, "熔深控制": 72, "焊接速度": 74},
        "ai_summary": "初始检测数据，夹渣问题较为常见，建议加强焊缝清洁"
    },
    # +5分钟后
    {
        "defect_radar": {"夹渣": 52, "气孔": 40, "焊瘤": 28, "咬边": 25, "未熔合": 20, "裂纹": 14},
        "skill_radar": {"光滑度": 75, "间距控制": 77, "缺陷控制": 73, "焊缝宽度": 71, "熔深控制": 74, "焊接速度": 76},
        "ai_summary": "数据持续积累中，夹渣问题仍需重点关注"
    },
    # +10分钟后
    {
        "defect_radar": {"夹渣": 58, "气孔": 48, "焊瘤": 32, "咬边": 28, "未熔合": 22, "裂纹": 16},
        "skill_radar": {"光滑度": 78, "间距控制": 79, "缺陷控制": 76, "焊缝宽度": 74, "熔深控制": 76, "焊接速度": 78},
        "ai_summary": "检测数据稳步增长，建议针对性改进焊接手法"
    },
    # +15分钟后
    {
        "defect_radar": {"夹渣": 65, "气孔": 55, "焊瘤": 36, "咬边": 32, "未熔合": 25, "裂纹": 18},
        "skill_radar": {"光滑度": 81, "间距控制": 82, "缺陷控制": 79, "焊缝宽度": 77, "熔深控制": 79, "焊接速度": 80},
        "ai_summary": "整体趋势良好，夹渣和气孔问题需要重点改进"
    },
    # +20分钟后
    {
        "defect_radar": {"夹渣": 72, "气孔": 62, "焊瘤": 40, "咬边": 35, "未熔合": 28, "裂纹": 20},
        "skill_radar": {"光滑度": 84, "间距控制": 84, "缺陷控制": 82, "焊缝宽度": 80, "熔深控制": 81, "焊接速度": 83},
        "ai_summary": "数据积累充分，焊接质量整体向好"
    },
    # +25分钟后
    {
        "defect_radar": {"夹渣": 78, "气孔": 68, "焊瘤": 44, "咬边": 38, "未熔合": 30, "裂纹": 22},
        "skill_radar": {"光滑度": 87, "间距控制": 86, "缺陷控制": 85, "焊缝宽度": 83, "熔深控制": 83, "焊接速度": 85},
        "ai_summary": "技能水平稳步提升，继续保持练习节奏"
    },
    # +30分钟后（最高）
    {
        "defect_radar": {"夹渣": 85, "气孔": 75, "焊瘤": 48, "咬边": 42, "未熔合": 33, "裂纹": 25},
        "skill_radar": {"光滑度": 90, "间距控制": 88, "缺陷控制": 88, "焊缝宽度": 86, "熔深控制": 86, "焊接速度": 88},
        "ai_summary": "检测周期完成，焊接技能显著提升，夹渣问题改善明显"
    }
]

# 当前数据索引（用于5分钟递增刷新）
_current_radar_index = 0
_last_radar_update_time = 0


@router.get("/predict/ai-radar-data", response_model=RadarDataResponse)
async def get_ai_radar_data(db: Session = Depends(get_db)):
    """
    获取雷达图数据（每5分钟递增刷新，数据呈增长趋势）

    刷新规则：
    - 程序启动后每5分钟自动递增到下一组数据
    - 数据呈缓慢增长趋势
    - 到达最高点后循环回第一组
    """
    import time
    global _current_radar_index, _last_radar_update_time

    current_time = time.time()
    REFRESH_INTERVAL = 300  # 5分钟 = 300秒

    # 检查是否需要递增到下一组数据
    if current_time - _last_radar_update_time >= REFRESH_INTERVAL:
        _current_radar_index = (_current_radar_index + 1) % len(_MOCK_RADAR_DATA)
        _last_radar_update_time = current_time

    # 获取当前索引的数据
    mock_data = _MOCK_RADAR_DATA[_current_radar_index]

    return RadarDataResponse(
        defect_radar=mock_data["defect_radar"],
        skill_radar=mock_data["skill_radar"],
        ai_summary=mock_data["ai_summary"],
        analysis_time=datetime.now().isoformat(),
        data_source="MOCK_DATA"
    )