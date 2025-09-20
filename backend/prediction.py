import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from typing import Dict
import warnings
warnings.filterwarnings('ignore')


def predict_future_scores(data: pd.DataFrame, days: int = 5) -> Dict[str, Dict[str, float]]:
    """
    使用随机森林回归预测未来几天的得分情况
    
    参数：
    - data: DataFrame，包含历史数据，格式为[t, x, y, z, score]
    - days: int，预测的天数，默认为5天
    
    返回：
    - dict: 包含历史数据和预测数据的字典
      {
        "history": {t: score},   # 实际数据，t为时间戳字符串
        "forecast": {t: score}   # 预测数据，t为时间戳字符串
      }
    """
    
    # 验证输入数据
    if data.empty:
        raise ValueError("输入数据不能为空")
    
    required_columns = ['t', 'x', 'y', 'z', 'score']
    if not all(col in data.columns for col in required_columns):
        raise ValueError(f"数据必须包含以下列: {required_columns}")
    
    # 复制数据以避免修改原始数据
    df = data.copy()
    
    # 确保时间列是datetime类型
    if not pd.api.types.is_datetime64_any_dtype(df['t']):
        df['t'] = pd.to_datetime(df['t'])
    
    # 按时间排序
    df = df.sort_values('t').reset_index(drop=True)
    
    # 创建特征工程
    # 1. 时间特征
    df['day_of_year'] = df['t'].dt.dayofyear
    df['day_of_week'] = df['t'].dt.dayofweek
    df['hour'] = df['t'].dt.hour
    
    # 2. 滞后特征（如果数据足够多）
    if len(df) >= 3:
        df['score_lag1'] = df['score'].shift(1)
        df['score_lag2'] = df['score'].shift(2)
        df['x_lag1'] = df['x'].shift(1)
        df['y_lag1'] = df['y'].shift(1)
        df['z_lag1'] = df['z'].shift(1)
    
    # 3. 移动平均特征
    if len(df) >= 3:
        df['score_ma3'] = df['score'].rolling(window=3, min_periods=1).mean()
        df['x_ma3'] = df['x'].rolling(window=3, min_periods=1).mean()
        df['y_ma3'] = df['y'].rolling(window=3, min_periods=1).mean()
        df['z_ma3'] = df['z'].rolling(window=3, min_periods=1).mean()
    
    # 4. 趋势特征
    df['time_index'] = range(len(df))
    
    # 准备特征
    feature_columns = ['x', 'y', 'z', 'day_of_year', 'day_of_week', 'hour', 'time_index']
    
    # 添加可用的滞后特征和移动平均特征
    if len(df) >= 3:
        feature_columns.extend(['score_lag1', 'score_lag2', 'x_lag1', 'y_lag1', 'z_lag1'])
        feature_columns.extend(['score_ma3', 'x_ma3', 'y_ma3', 'z_ma3'])
    
    # 删除包含NaN的行（由于滞后特征产生）
    df_clean = df.dropna()
    
    if len(df_clean) < 3:
        # 如果清理后数据太少，使用简单特征
        df_clean = df.copy()
        feature_columns = ['x', 'y', 'z', 'day_of_year', 'day_of_week', 'hour', 'time_index']
    
    # 准备训练数据
    X = df_clean[feature_columns]
    y = df_clean['score']
    
    # 特征标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 训练随机森林模型
    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        min_samples_split=2,
        min_samples_leaf=1
    )
    
    rf_model.fit(X_scaled, y)
    
    # 准备历史数据返回格式
    history = {}
    for _, row in df.iterrows():
        timestamp_str = row['t'].strftime('%Y-%m-%d %H:%M:%S')
        history[timestamp_str] = round(float(row['score']), 2)
    
    # 生成未来时间点
    last_time = df['t'].max()
    future_times = []
    for i in range(1, days + 1):
        future_time = last_time + timedelta(days=i)
        future_times.append(future_time)
    
    # 预测未来数据
    forecast = {}
    
    for i, future_time in enumerate(future_times):
        # 构建未来时间点的特征
        future_features = {}
        
        # 时间特征
        future_features['day_of_year'] = future_time.dayofyear
        future_features['day_of_week'] = future_time.dayofweek
        future_features['hour'] = future_time.hour
        future_features['time_index'] = len(df) + i
        
        # 基于历史趋势预测x, y, z值
        # 使用简单的线性趋势外推
        if len(df) >= 2:
            # 计算最近的趋势
            recent_data = df.tail(min(5, len(df)))
            
            x_trend = np.polyfit(range(len(recent_data)), recent_data['x'], 1)[0]
            y_trend = np.polyfit(range(len(recent_data)), recent_data['y'], 1)[0]
            z_trend = np.polyfit(range(len(recent_data)), recent_data['z'], 1)[0]
            
            # 添加一些随机波动
            np.random.seed(42 + i)  # 确保结果可重现
            x_noise = np.random.normal(0, 2)
            y_noise = np.random.normal(0, 2)
            z_noise = np.random.normal(0, 2)
            
            future_features['x'] = np.clip(df['x'].iloc[-1] + x_trend * (i + 1) + x_noise, 0, 100)
            future_features['y'] = np.clip(df['y'].iloc[-1] + y_trend * (i + 1) + y_noise, 0, 100)
            future_features['z'] = np.clip(df['z'].iloc[-1] + z_trend * (i + 1) + z_noise, 0, 100)
        else:
            # 如果数据不够，使用最后的值加小的随机变化
            future_features['x'] = np.clip(df['x'].iloc[-1] + np.random.normal(0, 1), 0, 100)
            future_features['y'] = np.clip(df['y'].iloc[-1] + np.random.normal(0, 1), 0, 100)
            future_features['z'] = np.clip(df['z'].iloc[-1] + np.random.normal(0, 1), 0, 100)
        
        # 滞后特征和移动平均特征（如果模型需要）
        if len(df_clean) >= 3 and 'score_lag1' in feature_columns:
            if i == 0:
                future_features['score_lag1'] = df['score'].iloc[-1]
                future_features['score_lag2'] = df['score'].iloc[-2] if len(df) >= 2 else df['score'].iloc[-1]
                future_features['x_lag1'] = df['x'].iloc[-1]
                future_features['y_lag1'] = df['y'].iloc[-1]
                future_features['z_lag1'] = df['z'].iloc[-1]
                
                future_features['score_ma3'] = df['score'].tail(3).mean()
                future_features['x_ma3'] = df['x'].tail(3).mean()
                future_features['y_ma3'] = df['y'].tail(3).mean()
                future_features['z_ma3'] = df['z'].tail(3).mean()
            else:
                # 使用之前预测的值作为滞后特征
                prev_scores = [v for v in forecast.values()]
                if len(prev_scores) >= 1:
                    future_features['score_lag1'] = prev_scores[-1]
                else:
                    future_features['score_lag1'] = df['score'].iloc[-1]
                
                if len(prev_scores) >= 2:
                    future_features['score_lag2'] = prev_scores[-2]
                else:
                    future_features['score_lag2'] = df['score'].iloc[-1]
                
                future_features['x_lag1'] = future_features['x']
                future_features['y_lag1'] = future_features['y']
                future_features['z_lag1'] = future_features['z']
                
                # 移动平均使用最近的预测值
                recent_scores = list(df['score'].tail(2)) + prev_scores
                future_features['score_ma3'] = np.mean(recent_scores[-3:])
                future_features['x_ma3'] = future_features['x']
                future_features['y_ma3'] = future_features['y']
                future_features['z_ma3'] = future_features['z']
        
        # 构建特征向量
        X_future = np.array([[future_features[col] for col in feature_columns]])
        X_future_scaled = scaler.transform(X_future)
        
        # 预测
        predicted_score = rf_model.predict(X_future_scaled)[0]
        
        # 确保预测值在合理范围内
        predicted_score = np.clip(predicted_score, 0, 100)
        
        timestamp_str = future_time.strftime('%Y-%m-%d %H:%M:%S')
        forecast[timestamp_str] = round(float(predicted_score), 2)
    
    return {
        "history": history,
        "forecast": forecast
    }


def test_prediction():
    """
    测试预测函数
    """
    # 导入数据生成器
    from data_generator import generate_dataset
    
    # 生成测试数据
    test_data = generate_dataset()
    
    print("测试数据形状:", test_data.shape)
    print("\n测试数据前5行:")
    print(test_data.head())
    
    # 测试预测函数
    result = predict_future_scores(test_data, days=5)
    
    print("\n预测结果:")
    print(f"历史数据点数: {len(result['history'])}")
    print(f"预测数据点数: {len(result['forecast'])}")
    
    print("\n最后5个历史数据点:")
    history_items = list(result['history'].items())
    for timestamp, score in history_items[-5:]:
        print(f"{timestamp}: {score}")
    
    print("\n预测的5天数据:")
    for timestamp, score in result['forecast'].items():
        print(f"{timestamp}: {score}")
    
    return result


if __name__ == "__main__":
    # 运行测试
    test_prediction()