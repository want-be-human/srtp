import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from typing import Dict
import warnings
warnings.filterwarnings('ignore')


def predict_future_scores(data: pd.DataFrame, days: int = 5) -> Dict[str, Dict[str, float]]:
    """用随机森林外推未来若干次检测的得分。

    教学场景下数据按检测次数采样（一节课可能 20+ 次），所以唯一的"时间"特征
    是 attempt_index 整数序号，配合 lag/MA 和三项子分数。返回的 history /
    forecast 仍以时间戳字符串为键，line_chart 等下游沿用旧契约。
    """

    if data.empty:
        raise ValueError("输入数据不能为空")

    required_columns = ['t', 'x', 'y', 'z', 'score']
    if not all(col in data.columns for col in required_columns):
        raise ValueError(f"数据必须包含以下列: {required_columns}")

    df = data.copy()

    if not pd.api.types.is_datetime64_any_dtype(df['t']):
        df['t'] = pd.to_datetime(df['t'])

    # 按时间排序后，行号即 attempt_index（"第几次检测"），是唯一的时间特征
    df = df.sort_values('t').reset_index(drop=True)

    # 滞后 + 3 点滑动平均给 RF 捕捉短期节奏；样本不足时跳过避免大量 NaN
    if len(df) >= 3:
        df['score_lag1'] = df['score'].shift(1)
        df['score_lag2'] = df['score'].shift(2)
        df['x_lag1'] = df['x'].shift(1)
        df['y_lag1'] = df['y'].shift(1)
        df['z_lag1'] = df['z'].shift(1)
        df['score_ma3'] = df['score'].rolling(window=3, min_periods=1).mean()
        df['x_ma3'] = df['x'].rolling(window=3, min_periods=1).mean()
        df['y_ma3'] = df['y'].rolling(window=3, min_periods=1).mean()
        df['z_ma3'] = df['z'].rolling(window=3, min_periods=1).mean()

    df['attempt_index'] = range(len(df))

    feature_columns = ['x', 'y', 'z', 'attempt_index']

    if len(df) >= 3:
        feature_columns.extend(['score_lag1', 'score_lag2', 'x_lag1', 'y_lag1', 'z_lag1'])
        feature_columns.extend(['score_ma3', 'x_ma3', 'y_ma3', 'z_ma3'])

    df_clean = df.dropna()

    if len(df_clean) < 3:
        df_clean = df.copy()
        feature_columns = ['x', 'y', 'z', 'attempt_index']

    X = df_clean[feature_columns]
    y = df_clean['score']

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        min_samples_split=2,
        min_samples_leaf=1
    )

    rf_model.fit(X_scaled, y)

    # 字典键存时间戳字符串；重复时间戳累加 1s 偏移避免互相覆盖
    history = {}
    for _, row in df.iterrows():
        timestamp_str = row['t'].strftime('%Y-%m-%d %H:%M:%S')
        while timestamp_str in history:
            row_t = pd.to_datetime(timestamp_str) + timedelta(seconds=1)
            timestamp_str = row_t.strftime('%Y-%m-%d %H:%M:%S')
        history[timestamp_str] = round(float(row['score']), 2)

    last_time = df['t'].max()
    future_times = []
    for i in range(1, days + 1):
        future_time = last_time + timedelta(days=i)
        future_times.append(future_time)

    forecast = {}

    for i, future_time in enumerate(future_times):
        future_features = {}
        future_features['attempt_index'] = len(df) + i

        if len(df) >= 2:
            # 用最近 ≤5 条做线性外推，固定种子保持预测可重现
            recent_data = df.tail(min(5, len(df)))

            x_trend = np.polyfit(range(len(recent_data)), recent_data['x'], 1)[0]
            y_trend = np.polyfit(range(len(recent_data)), recent_data['y'], 1)[0]
            z_trend = np.polyfit(range(len(recent_data)), recent_data['z'], 1)[0]

            np.random.seed(42 + i)
            x_noise = np.random.normal(0, 2)
            y_noise = np.random.normal(0, 2)
            z_noise = np.random.normal(0, 2)

            x_last = float(df['x'].iloc[-1])
            y_last = float(df['y'].iloc[-1])
            z_last = float(df['z'].iloc[-1])

            future_features['x'] = float(np.clip(x_last + x_trend * (i + 1) + x_noise, 0, 100))
            future_features['y'] = float(np.clip(y_last + y_trend * (i + 1) + y_noise, 0, 100))
            future_features['z'] = float(np.clip(z_last + z_trend * (i + 1) + z_noise, 0, 100))
        else:
            x_last = float(df['x'].iloc[-1])
            y_last = float(df['y'].iloc[-1])
            z_last = float(df['z'].iloc[-1])

            future_features['x'] = float(np.clip(x_last + np.random.normal(0, 1), 0, 100))
            future_features['y'] = float(np.clip(y_last + np.random.normal(0, 1), 0, 100))
            future_features['z'] = float(np.clip(z_last + np.random.normal(0, 1), 0, 100))

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
                # 递推：用前几步已预测出的 score 喂 lag/ma 特征
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

                recent_scores = list(df['score'].tail(2)) + prev_scores
                future_features['score_ma3'] = np.mean(recent_scores[-3:])
                future_features['x_ma3'] = future_features['x']
                future_features['y_ma3'] = future_features['y']
                future_features['z_ma3'] = future_features['z']

        X_future = np.array([[future_features[col] for col in feature_columns]])
        X_future_scaled = scaler.transform(X_future)

        predicted_score = rf_model.predict(X_future_scaled)[0]
        predicted_score = np.clip(predicted_score, 0, 100)

        timestamp_str = future_time.strftime('%Y-%m-%d %H:%M:%S')
        forecast[timestamp_str] = round(float(predicted_score), 2)
    
    return {
        "history": history,
        "forecast": forecast
    }


def predict_with_temporal_model(data: pd.DataFrame, days: int = 5) -> Dict[str, Dict[str, float]]:
    """1D-CNN 深度预测，返回结构和 predict_future_scores 一致；样本不足时透明回退 RF。"""
    if data.empty:
        raise ValueError("输入数据不能为空")

    df = data.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['t']):
        df['t'] = pd.to_datetime(df['t'])
    df = df.sort_values('t').reset_index(drop=True)

    history = {}
    for _, row in df.iterrows():
        ts = row['t'].strftime('%Y-%m-%d %H:%M:%S')
        while ts in history:
            ts = (pd.to_datetime(ts) + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
        history[ts] = round(float(row['score']), 2)

    records = [
        {
            "smoothness_score": float(r["x"]),
            "width_score": float(r["y"]),
            "defect_score": float(r["z"]),
            "total_score": float(r["score"]),
        }
        for _, r in df.iterrows()
    ]

    try:
        from services.prediction import temporal_model
    except ImportError:
        return predict_future_scores(data, days=days)

    model = temporal_model.get_or_train(records)
    if model is None:
        # 样本太少，回退到 RF，前端拿到的依旧是合法的 forecast
        return predict_future_scores(data, days=days)

    preds = temporal_model.forecast(model, records[-temporal_model.MAX_INFER_WINDOW:])
    # forecast 字段沿用时间戳键以兼容现有下游（line_chart 等）
    last_time = df['t'].max()
    forecast_out = {}
    for i, score in enumerate(preds[:days], start=1):
        ts = (last_time + timedelta(days=i)).strftime('%Y-%m-%d %H:%M:%S')
        forecast_out[ts] = round(float(score), 2)

    return {"history": history, "forecast": forecast_out}


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
    test_prediction()