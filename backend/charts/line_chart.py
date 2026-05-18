import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import base64
import io
from datetime import datetime
from typing import Dict

# 设置matplotlib的中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def plot_prediction_chart(history: Dict[str, float], forecast: Dict[str, float]) -> str:
    """
    绘制预测图表，包含历史数据（实线）和预测数据（虚线）
    
    参数：
    - history: dict，历史数据，格式为 {时间戳字符串: 得分}
    - forecast: dict，预测数据，格式为 {时间戳字符串: 得分}
    
    返回：
    - str: base64编码的图片字符串
    """
    
    # 数据验证
    if not history:
        raise ValueError("历史数据不能为空")
    if not forecast:
        raise ValueError("预测数据不能为空")
    
    # 转换数据格式
    hist_times = []
    hist_scores = []
    for time_str, score in history.items():
        try:
            hist_times.append(datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S'))
            hist_scores.append(float(score))
        except ValueError:
            # 如果解析失败，尝试其他格式
            try:
                hist_times.append(datetime.strptime(time_str, '%Y-%m-%d'))
                hist_scores.append(float(score))
            except ValueError:
                continue
    
    forecast_times = []
    forecast_scores = []
    for time_str, score in forecast.items():
        try:
            forecast_times.append(datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S'))
            forecast_scores.append(float(score))
        except ValueError:
            try:
                forecast_times.append(datetime.strptime(time_str, '%Y-%m-%d'))
                forecast_scores.append(float(score))
            except ValueError:
                continue
    
    if not hist_times or not forecast_times:
        raise ValueError("无法解析时间数据")
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 绘制历史数据（实线）
    ax.plot(hist_times, hist_scores, 
            color='#2E86AB', 
            linewidth=2.5, 
            marker='o', 
            markersize=4,
            label='实际数据', 
            linestyle='-')
    
    # 绘制预测数据（虚线）
    # 连接历史数据的最后一个点和预测数据的第一个点
    if hist_times and forecast_times:
        # 连接线
        ax.plot([hist_times[-1], forecast_times[0]], 
                [hist_scores[-1], forecast_scores[0]], 
                color='#A23B72', 
                linewidth=2,
                linestyle='--',
                alpha=0.7)
    
    ax.plot(forecast_times, forecast_scores, 
            color='#A23B72', 
            linewidth=2.5, 
            marker='s', 
            markersize=4,
            label='预测数据', 
            linestyle='--')
    
    # 设置图表样式
    ax.set_title('焊缝质量预测趋势图', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('时间', fontsize=12)
    ax.set_ylabel('综合评分', fontsize=12)
    
    # 设置网格
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    
    # 设置图例
    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)
    
    # 设置时间轴格式
    all_times = hist_times + forecast_times
    time_range = max(all_times) - min(all_times)
    
    if time_range.days > 30:
        # 超过30天，按月显示
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    elif time_range.days > 7:
        # 7-30天，按周显示
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator())
    else:
        # 7天以内，按天显示
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator())
    
    # 旋转时间标签以避免重叠
    plt.xticks(rotation=45)
    
    # 设置Y轴范围
    all_scores = hist_scores + forecast_scores
    y_min = max(0, min(all_scores) - 5)
    y_max = min(100, max(all_scores) + 5)
    ax.set_ylim(y_min, y_max)
    
    # 添加预测分界线
    if hist_times and forecast_times:
        divider_x = hist_times[-1]
        ax.axvline(x=divider_x, color='gray', linestyle=':', alpha=0.7, linewidth=1)
        
        # 添加文本标注
        ax.text(divider_x, y_max - (y_max - y_min) * 0.1, 
                '预测开始', 
                rotation=90, 
                verticalalignment='top',
                horizontalalignment='right',
                fontsize=9,
                alpha=0.7)
    
    # 调整布局
    plt.tight_layout()
    
    # 将图片转换为base64字符串
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    
    # 编码为base64
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # 清理内存
    plt.close(fig)
    buffer.close()
    
    return image_base64


def plot_prediction_chart_with_prefix(history: Dict[str, float], forecast: Dict[str, float]) -> str:
    """
    绘制预测图表并返回带有data URL前缀的base64字符串
    
    参数：
    - history: dict，历史数据
    - forecast: dict，预测数据
    
    返回：
    - str: 完整的data URL字符串，可直接用于HTML img标签
    """
    base64_str = plot_prediction_chart(history, forecast)
    return f"data:image/png;base64,{base64_str}"


def test_chart():
    """
    测试图表绘制功能
    """
    # 导入预测函数进行测试
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    from prediction import predict_future_scores
    from data_generator import generate_dataset
    
    print("正在生成测试数据...")
    test_data = generate_dataset()
    
    print("正在进行预测...")
    result = predict_future_scores(test_data, days=5)
    
    print("正在绘制图表...")
    base64_image = plot_prediction_chart(result['history'], result['forecast'])
    
    print("图表生成成功!")
    print(f"Base64字符串长度: {len(base64_image)}")
    print(f"Base64前100字符: {base64_image[:100]}...")
    
    # 生成带前缀的版本
    data_url = plot_prediction_chart_with_prefix(result['history'], result['forecast'])
    print(f"Data URL长度: {len(data_url)}")
    print(f"Data URL前100字符: {data_url[:100]}...")
    
    return base64_image


if __name__ == "__main__":
    # 运行测试
    test_chart()
