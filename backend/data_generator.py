import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_dataset():
    """
    生成30条模拟数据，格式为[t, x, y, z, score]

    参数说明：
    - t: 时间戳
    - x: 光滑度 (0-100)
    - y: 间距 (0-100)
    - z: 缺陷类型 (0-100)
    - score: 综合评分 = 0.33*x + 0.33*y + 0.34*z
    
    所有值范围在0-100之间，趋势为"波动上升"（非平滑稳定上升）
    
    Returns:
        pandas.DataFrame: 包含30条模拟数据的DataFrame
    """
    
    # 设置随机种子以保证结果可复现
    np.random.seed(42)
    
    # 生成时间序列
    start_time = datetime.now() - timedelta(days=29)
    timestamps = [start_time + timedelta(days=i) for i in range(30)]
    
    # 调整基础趋势，使最终分数集中在70-90之间，多数在85分左右
    # 为了得到总分集中在85分，各项分数应该平均在85分左右
    x_base_trend = np.linspace(82, 88, 30)  # 光滑度基础趋势：82-88，均值85
    y_base_trend = np.linspace(81, 87, 30)  # 间距基础趋势：81-87，均值84
    z_base_trend = np.linspace(83, 89, 30)  # 缺陷控制基础趋势：83-89，均值86

    # 添加适度波动性，保持分数在合理范围
    x_wave = 3 * np.sin(np.linspace(0, 4*np.pi, 30))  # 较小的正弦波动
    x_noise = np.random.normal(0, 2, 30)  # 较小的随机噪声
    x_values = x_base_trend + x_wave + x_noise
    x_values = np.clip(x_values, 75, 95)  # 限制在75-95范围内

    # 生成y值（间距）- 与x相关但有独立波动
    y_wave = 2.5 * np.sin(np.linspace(0.5*np.pi, 4.5*np.pi, 30))  # 不同相位的小波动
    y_noise = np.random.normal(0, 1.8, 30)  # 小噪声
    y_values = y_base_trend + y_wave + y_noise
    y_values = np.clip(y_values, 75, 95)

    # 生成z值（缺陷控制）- 稍大的波动性但控制范围
    z_wave = 3.5 * np.sin(np.linspace(np.pi, 5*np.pi, 30))  # 适度幅度的波动
    z_noise = np.random.normal(0, 2.2, 30)  # 适度噪声
    z_values = z_base_trend + z_wave + z_noise
    z_values = np.clip(z_values, 75, 95)

    # 计算综合评分
    scores = 0.33 * x_values + 0.33 * y_values + 0.34 * z_values

    # 对分数进行后处理，使其更集中在85分左右
    score_adjustment = np.random.normal(0, 1.5, 30)  # 小幅随机调整
    scores = scores + score_adjustment

    # 最终限制总分在70-90范围内，但主要集中在80-90
    scores = np.clip(scores, 70, 90)
    
    # 创建DataFrame
    data = {
        't': timestamps,
        'x': x_values.round(2),
        'y': y_values.round(2), 
        'z': z_values.round(2),
        'score': scores.round(2)
    }
    
    df = pd.DataFrame(data)
    
    return df


def preview_dataset():
    """
    预览生成的数据集
    """
    df = generate_dataset()
    print("生成的数据集预览：")
    print(f"数据形状：{df.shape}")
    print("\n前5行数据：")
    print(df.head())
    print("\n后5行数据：")
    print(df.tail())
    print("\n数据统计信息：")
    print(df.describe())
    
    return df


if __name__ == "__main__":
    # 当直接运行此文件时，预览生成的数据
    preview_dataset()