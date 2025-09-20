import matplotlib.pyplot as plt
import numpy as np
import base64
import io
from typing import Dict
import math

# 设置matplotlib的中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def _create_radar_chart_base(labels, values, title, color='#2E86AB', alpha=0.3):
    """
    创建雷达图的基础函数
    
    参数：
    - labels: 维度标签列表
    - values: 对应的数值列表
    - title: 图表标题
    - color: 填充颜色
    - alpha: 透明度
    
    返回：
    - base64编码的图片字符串
    """
    # 验证输入数据
    if not labels or not values:
        raise ValueError("标签和数值不能为空")
    
    if len(labels) != len(values):
        raise ValueError("标签和数值的长度必须一致")
    
    # 确保所有值在0-100范围内
    values = [max(0, min(100, float(v))) for v in values]
    
    # 计算角度
    N = len(labels)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]  # 闭合图形
    
    # 添加第一个值到末尾以闭合图形
    values += values[:1]
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    # 绘制数据
    ax.plot(angles, values, 'o-', linewidth=2, color=color, markersize=6)
    ax.fill(angles, values, alpha=alpha, color=color)
    
    # 设置标签
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=12)
    
    # 设置Y轴
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=10, alpha=0.7)
    
    # 添加网格
    ax.grid(True, alpha=0.3)
    
    # 设置标题
    plt.title(title, size=16, fontweight='bold', pad=30)
    
    # 在每个维度点上显示数值
    for angle, value, label in zip(angles[:-1], values[:-1], labels):
        # 计算文本位置
        x_pos = angle
        y_pos = value + 5  # 稍微向外偏移
        
        # 确保文本不超出边界
        if y_pos > 100:
            y_pos = value - 8
        
        ax.text(x_pos, y_pos, f'{value:.0f}', 
                ha='center', va='center', 
                fontsize=10, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    # 调整布局
    plt.tight_layout()
    
    # 转换为base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # 清理内存
    plt.close(fig)
    buffer.close()
    
    return image_base64


def plot_defect_radar(data: Dict[str, float]) -> str:
    """
    绘制缺陷类别雷达图
    
    参数：
    - data: dict，缺陷数据，例如 {"气孔": 70, "夹渣": 50, ...}
            支持的维度：气孔、夹渣、未熔合、焊瘤、咬边、裂纹
    
    返回：
    - str: base64编码的图片字符串
    """
    # 定义标准维度
    standard_labels = ['气孔', '夹渣', '未熔合', '焊瘤', '咬边', '裂纹']
    
    # 验证数据
    if not data:
        raise ValueError("缺陷数据不能为空")
    
    # 提取数值，如果某个维度缺失则使用0
    values = []
    for label in standard_labels:
        values.append(data.get(label, 0))
    
    # 检查是否所有值都为0
    if all(v == 0 for v in values):
        # 如果所有标准维度都为0，使用传入数据的前6个
        available_items = list(data.items())[:6]
        if available_items:
            labels = [item[0] for item in available_items]
            values = [item[1] for item in available_items]
            # 如果不足6个维度，用0补充
            while len(labels) < 6:
                labels.append(f'维度{len(labels)+1}')
                values.append(0)
        else:
            raise ValueError("数据中没有有效的缺陷信息")
    else:
        labels = standard_labels
    
    return _create_radar_chart_base(
        labels=labels,
        values=values,
        title='焊缝缺陷分析雷达图',
        color='#E74C3C',  # 红色系，表示缺陷
        alpha=0.25
    )


def plot_skill_radar(data: Dict[str, float]) -> str:
    """
    绘制操作手法雷达图
    
    参数：
    - data: dict，手法数据，例如 {"速度": 80, "角度": 70, ...}
            支持的维度：速度、角度、深度、X光、平整度、光滑度
    
    返回：
    - str: base64编码的图片字符串
    """
    # 定义标准维度
    standard_labels = ['速度', '角度', '深度', 'X光', '平整度', '光滑度']
    
    # 验证数据
    if not data:
        raise ValueError("手法数据不能为空")
    
    # 提取数值，如果某个维度缺失则使用0
    values = []
    for label in standard_labels:
        values.append(data.get(label, 0))
    
    # 检查是否所有值都为0
    if all(v == 0 for v in values):
        # 如果所有标准维度都为0，使用传入数据的前6个
        available_items = list(data.items())[:6]
        if available_items:
            labels = [item[0] for item in available_items]
            values = [item[1] for item in available_items]
            # 如果不足6个维度，用0补充
            while len(labels) < 6:
                labels.append(f'维度{len(labels)+1}')
                values.append(0)
        else:
            raise ValueError("数据中没有有效的手法信息")
    else:
        labels = standard_labels
    
    return _create_radar_chart_base(
        labels=labels,
        values=values,
        title='焊接操作手法雷达图',
        color='#27AE60',  # 绿色系，表示技能
        alpha=0.25
    )


def plot_defect_radar_with_prefix(data: Dict[str, float]) -> str:
    """
    绘制缺陷雷达图并返回带有data URL前缀的base64字符串
    """
    base64_str = plot_defect_radar(data)
    return f"data:image/png;base64,{base64_str}"


def plot_skill_radar_with_prefix(data: Dict[str, float]) -> str:
    """
    绘制手法雷达图并返回带有data URL前缀的base64字符串
    """
    base64_str = plot_skill_radar(data)
    return f"data:image/png;base64,{base64_str}"


def generate_sample_data():
    """
    生成示例数据用于测试
    """
    # 模拟缺陷数据
    defect_data = {
        '气孔': np.random.uniform(10, 90),
        '夹渣': np.random.uniform(10, 90),
        '未熔合': np.random.uniform(10, 90),
        '焊瘤': np.random.uniform(10, 90),
        '咬边': np.random.uniform(10, 90),
        '裂纹': np.random.uniform(10, 90)
    }
    
    # 模拟手法数据
    skill_data = {
        '速度': np.random.uniform(40, 95),
        '角度': np.random.uniform(40, 95),
        '深度': np.random.uniform(40, 95),
        'X光': np.random.uniform(40, 95),
        '平整度': np.random.uniform(40, 95),
        '光滑度': np.random.uniform(40, 95)
    }
    
    return defect_data, skill_data


def test_radar_charts():
    """
    测试雷达图绘制功能
    """
    print("正在生成示例数据...")
    
    # 设置随机种子以获得一致的结果
    np.random.seed(42)
    
    defect_data, skill_data = generate_sample_data()
    
    print("缺陷数据:", {k: f"{v:.1f}" for k, v in defect_data.items()})
    print("手法数据:", {k: f"{v:.1f}" for k, v in skill_data.items()})
    
    print("\n正在绘制缺陷雷达图...")
    try:
        defect_base64 = plot_defect_radar(defect_data)
        print("缺陷雷达图生成成功!")
        print(f"Base64长度: {len(defect_base64)}")
        print(f"Base64前100字符: {defect_base64[:100]}...")
    except Exception as e:
        print(f"缺陷雷达图生成失败: {e}")
        return False
    
    print("\n正在绘制手法雷达图...")
    try:
        skill_base64 = plot_skill_radar(skill_data)
        print("手法雷达图生成成功!")
        print(f"Base64长度: {len(skill_base64)}")
        print(f"Base64前100字符: {skill_base64[:100]}...")
    except Exception as e:
        print(f"手法雷达图生成失败: {e}")
        return False
    
    print("\n测试Data URL格式...")
    try:
        defect_data_url = plot_defect_radar_with_prefix(defect_data)
        skill_data_url = plot_skill_radar_with_prefix(skill_data)
        
        print(f"缺陷图Data URL长度: {len(defect_data_url)}")
        print(f"手法图Data URL长度: {len(skill_data_url)}")
        
        # 验证格式
        if defect_data_url.startswith("data:image/png;base64,"):
            print("缺陷图Data URL格式正确")
        else:
            print("缺陷图Data URL格式错误")
            
        if skill_data_url.startswith("data:image/png;base64,"):
            print("手法图Data URL格式正确")
        else:
            print("手法图Data URL格式错误")
            
    except Exception as e:
        print(f"Data URL测试失败: {e}")
        return False
    
    print("\n所有雷达图测试通过!")
    return True


if __name__ == "__main__":
    # 运行测试
    test_radar_charts()
