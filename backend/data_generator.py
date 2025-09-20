import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_dataset():
    """
    生成30条模拟数据，格式为[t, x, y, z, score]
    
    参数说明：
    - t: 时间戳
    - x: 宽度 (0-100)
    - y: 光滑度 (0-100) 
    - z: 缺陷类别标准 (0-100)
    - score: 综合评分 = 0.3*x + 0.3*y + 0.4*z
    
    所有值范围在0-100之间，趋势为"波动上升"（非平滑稳定上升）
    
    Returns:
        pandas.DataFrame: 包含30条模拟数据的DataFrame
    """
    
    # 设置随机种子以保证结果可复现
    np.random.seed(42)
    
    # 生成时间序列
    start_time = datetime.now() - timedelta(days=29)
    timestamps = [start_time + timedelta(days=i) for i in range(30)]
    
    # 生成波动上升的基础趋势
    base_trend = np.linspace(20, 80, 30)  # 从20到80的基础上升趋势
    
    # 添加波动性 - 使用正弦波和随机噪声
    wave_component = 10 * np.sin(np.linspace(0, 4*np.pi, 30))  # 正弦波动
    random_noise = np.random.normal(0, 8, 30)  # 随机噪声
    
    # 生成x值（宽度）- 波动上升
    x_values = base_trend + wave_component + random_noise
    x_values = np.clip(x_values, 0, 100)  # 限制在0-100范围内
    
    # 生成y值（光滑度）- 与x相关但有独立波动
    y_base_trend = np.linspace(15, 85, 30)
    y_wave = 12 * np.sin(np.linspace(0.5*np.pi, 4.5*np.pi, 30))  # 不同相位的波动
    y_noise = np.random.normal(0, 6, 30)
    y_values = y_base_trend + y_wave + y_noise
    y_values = np.clip(y_values, 0, 100)
    
    # 生成z值（缺陷类别标准）- 更大的波动性
    z_base_trend = np.linspace(25, 75, 30)
    z_wave = 15 * np.sin(np.linspace(np.pi, 5*np.pi, 30))  # 更大幅度的波动
    z_noise = np.random.normal(0, 10, 30)
    z_values = z_base_trend + z_wave + z_noise
    z_values = np.clip(z_values, 0, 100)
    
    # 计算综合评分
    scores = 0.3 * x_values + 0.3 * y_values + 0.4 * z_values
    
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