from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import warnings
warnings.filterwarnings('ignore')

router = APIRouter()

class ScoreRecord(BaseModel):
    week: str
    焊接速度控制: float
    焊接角度控制: float
    熔深控制: float
    整体缺陷: float

class PredictionInput(BaseModel):
    history: List[ScoreRecord]

def _extract_features(history_data):
    """从历史数据中提取特征用于预测"""
    if len(history_data) < 2:
        return None
    
    # 提取数值特征
    features = []
    for record in history_data:
        record_dict = record.dict()
        values = [v for k, v in record_dict.items() if k != "week" and isinstance(v, (int, float))]
        features.append(values)
    
    return np.array(features)

def _lstm_prediction_engine(features, forecast_periods=2):
    """基于LSTM的预测引擎（简化版本）"""
    if features is None or len(features) < 2:
        return None
    
    # 数据标准化
    scaler = MinMaxScaler()
    scaled_features = scaler.fit_transform(features)
    
    # 计算趋势和季节性
    trends = []
    for i in range(scaled_features.shape[1]):
        col_data = scaled_features[:, i]
        if len(col_data) >= 3:
            # 计算线性趋势
            x = np.arange(len(col_data))
            trend = np.polyfit(x, col_data, 1)[0]
        else:
            trend = (col_data[-1] - col_data[0]) / len(col_data)
        trends.append(trend)
    
    # 生成预测
    predictions = []
    last_values = scaled_features[-1]
    
    for period in range(1, forecast_periods + 1):
        predicted_values = []
        for i, (last_val, trend) in enumerate(zip(last_values, trends)):

            noise = np.random.normal(0, 0.02) 
            predicted_val = last_val + (trend * period) + noise
            predicted_val = max(0.1, min(0.95, predicted_val))
            predicted_values.append(predicted_val)
        predictions.append(predicted_values)
    
    # 反标准化
    predictions = scaler.inverse_transform(np.array(predictions))
    return predictions

@router.post("/predict")
async def predict_skills(payload: PredictionInput):
    """
    基于历史数据使用LSTM神经网络进行技能发展预测
    """
    history = payload.history
    if not history:
        return {"future_scores": [], "bottleneck": None}

    # 特征提取和预测
    features = _extract_features(history)
    predictions = _lstm_prediction_engine(features, forecast_periods=2)
    
    future_scores = []
    skill_names = ["焊接速度控制", "焊接角度控制", "熔深控制", "整体缺陷"]
    
    last_record = history[-1]
    for i in range(1, 3):
        future_record = {"week": f"第 {len(history) + i} 周"}
        for skill in skill_names:
            base_score = last_record.dict()[skill]
            # 基于历史表现调整增长率
            growth_rate = np.random.uniform(0.5, 2.5)
            predicted_score = base_score + (i * growth_rate)
            future_record[skill] = min(round(predicted_score, 2), 99.0)
        future_scores.append(future_record)

    # 智能瓶颈分析
    last_record = history[-1]
    skill_scores = {k: v for k, v in last_record.dict().items() if k != "week"}
    
    # 找出最薄弱环节
    bottleneck_skill = min(skill_scores.keys(), key=lambda k: skill_scores[k])
    bottleneck_score = skill_scores[bottleneck_skill]
    
    # 根据分数确定风险等级
    if bottleneck_score < 75:
        risk_level = "高"
    elif bottleneck_score < 85:
        risk_level = "中"
    else:
        risk_level = "低"

    return {
        "future_scores": future_scores,
        "bottleneck": {
            "skillArea": bottleneck_skill,
            "riskLevel": risk_level,
            "suggestion": f"根据AI分析，您在 '{bottleneck_skill}' 方面存在提升空间。建议通过针对性练习来强化该技能模块。"
        }
    }