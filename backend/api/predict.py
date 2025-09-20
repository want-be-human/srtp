from datetime import datetime
import logging
import os
import sys
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)


# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic 模型定义
class PredictionResponse(BaseModel):
    """预测接口返回模型"""
    history: Dict[str, float]
    forecast: Dict[str, float]
    line_chart: str
    defect_radar: str
    skill_radar: str

class PredictionStats(BaseModel):
    """预测统计信息模型"""
    total_data_points: int
    forecast_days: int
    prediction_accuracy: float
    last_updated: str

@router.get("/predict", response_model=PredictionResponse)
async def get_prediction():
    """
    获取焊缝质量预测数据和可视化图表
    
    调用顺序：
    1. generate_dataset() - 生成30条历史模拟数据
    2. predict_future_scores() - 预测未来5天得分
    3. plot_prediction_chart() - 生成预测趋势图
    4. plot_defect_radar() - 生成缺陷分析雷达图
    5. plot_skill_radar() - 生成操作手法雷达图
    
    Returns:
        PredictionResponse: 包含历史数据、预测数据和所有图表的base64字符串
    """
    try:
        logger.info("开始执行预测流程...")
        
        # 动态导入模块（如果之前导入失败）
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
        
        # 步骤1: 生成历史数据集
        logger.info("步骤1: 生成历史数据集...")
        historical_data = generate_dataset()
        logger.info(f"生成了 {len(historical_data)} 条历史数据")
        
        # 步骤2: 预测未来得分
        logger.info("步骤2: 执行预测算法...")
        prediction_result = predict_future_scores(historical_data, days=5)
        logger.info(f"预测完成，历史数据点: {len(prediction_result['history'])}, 预测数据点: {len(prediction_result['forecast'])}")
        
        # 步骤3: 生成预测趋势线性图
        logger.info("步骤3: 生成预测趋势图...")
        line_chart_base64 = plot_prediction_chart(
            prediction_result['history'], 
            prediction_result['forecast']
        )
        logger.info(f"趋势图生成完成，Base64长度: {len(line_chart_base64)}")
        
        # 步骤4: 生成缺陷分析雷达图
        logger.info("步骤4: 生成缺陷分析雷达图...")
        # 生成示例缺陷数据（在实际应用中，这些数据应该来自检测系统）
        defect_data, _ = generate_sample_data()
        defect_radar_base64 = plot_defect_radar(defect_data)
        logger.info(f"缺陷雷达图生成完成，Base64长度: {len(defect_radar_base64)}")
        
        # 步骤5: 生成操作手法雷达图
        logger.info("步骤5: 生成操作手法雷达图...")
        # 生成示例手法数据（在实际应用中，这些数据应该来自操作评估系统）
        _, skill_data = generate_sample_data()
        skill_radar_base64 = plot_skill_radar(skill_data)
        logger.info(f"手法雷达图生成完成，Base64长度: {len(skill_radar_base64)}")
        
        # 构建返回结果
        response = PredictionResponse(
            history=prediction_result['history'],
            forecast=prediction_result['forecast'],
            line_chart=line_chart_base64,
            defect_radar=defect_radar_base64,
            skill_radar=skill_radar_base64
        )
        
        logger.info("预测流程执行完成")
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
        from datetime import datetime
        
        stats = PredictionStats(
            total_data_points=30,
            forecast_days=5,
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
        days: 预测天数，默认5天
        
    Returns:
        自定义预测结果
    """
    try:
        logger.info(f"执行自定义预测，预测天数: {days}")
        
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
        
        # 这里可以处理用户传入的实时检测数据
        # 目前先使用默认数据集，实际应用中应该处理传入的data
        
        # 生成基础数据集
        base_data = generate_dataset()
        
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
        
        # 生成基础数据
        historical_data = generate_dataset()
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
        
        test_data = generate_dataset()
        test_result = predict_future_scores(test_data, days=1)
        
        return {
            "status": "healthy",
            "message": "预测服务运行正常",
            "test_data_points": len(test_data),
            "test_prediction_points": len(test_result['forecast']),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"预测服务异常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }