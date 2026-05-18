#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化后的宽度检测算法
"""

import cv2
import numpy as np
import sys
import os

# 添加父目录到路径
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.yolo.kuandu_jiance_qiqi import PreciseWeldDetector


def create_test_image():
    """创建测试图像（模拟焊缝）"""
    height, width = 480, 640
    image = np.zeros((height, width, 3), dtype=np.uint8)

    # 背景（灰色钢板）
    image[:, :] = [120, 120, 120]

    # 焊缝区域（中间，更亮）
    center_y = height // 2
    weld_height = 20  # 焊缝高度
    weld_top = center_y - weld_height // 2
    weld_bottom = center_y + weld_height // 2

    # 焊缝主体（银白色）
    image[weld_top:weld_bottom, :] = [200, 200, 200]

    # 焊缝边缘（渐变，模拟梯度）
    for i in range(5):
        image[weld_top - i, :] = [200 - i * 20, 200 - i * 20, 200 - i * 20]
        image[weld_bottom + i, :] = [200 - i * 20, 200 - i * 20, 200 - i * 20]

    return image


def test_algorithm():
    """测试算法"""
    print("测试优化后的宽度检测算法")
    print("=" * 50)

    # 创建检测器
    detector = PreciseWeldDetector(debug=True, image_height_cm=15.0)

    # 创建测试图像
    test_image = create_test_image()

    # 保存测试图像
    cv2.imwrite("test_weld_image.png", test_image)
    print("测试图像已保存: test_weld_image.png")

    # 运行检测
    result = detector.enhanced_weld_detection(test_image)

    # 打印结果
    print("\n检测结果:")
    print(f"  是否检测到: {result['found']}")
    print(f"  中心Y坐标: {result['center_y']}")
    print(f"  上边界Y: {result['top_y']}")
    print(f"  下边界Y: {result['bottom_y']}")
    print(f"  厚度(像素): {result['thickness']}")
    print(f"  厚度(mm): {result['thickness_mm']:.2f}")
    print(f"  融合分数: {result['fusion_score']:.4f}")

    # 验证结果
    expected_center = 240  # 图像高度480，中心是240
    tolerance = 10  # 允许10像素误差

    if result["found"]:
        if abs(result["center_y"] - expected_center) <= tolerance:
            print("\n✅ 测试通过: 成功检测到焊缝中心位置")
        else:
            print(f"\n⚠️  警告: 检测位置偏差较大")
            print(f"  期望中心: {expected_center}, 实际中心: {result['center_y']}")
    else:
        print("\n❌ 测试失败: 未检测到焊缝")

    # 可视化结果
    vis_image = test_image.copy()
    height, width = test_image.shape[:2]
    center_y = result["center_y"]
    top_y = result["top_y"]
    bottom_y = result["bottom_y"]

    # 绘制中心线（红色）
    cv2.line(vis_image, (0, center_y), (width - 1, center_y), (0, 0, 255), 2)

    # 绘制上下边界（绿色）
    cv2.line(vis_image, (0, top_y), (width - 1, top_y), (0, 255, 0), 2)
    cv2.line(vis_image, (0, bottom_y), (width - 1, bottom_y), (0, 255, 0), 2)

    # 绘制厚度区域（半透明蓝色）
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, top_y), (width - 1, bottom_y), (255, 0, 0), -1)
    cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)

    # 添加文本
    cv2.putText(
        vis_image,
        f"Thickness: {result['thickness_mm']:.1f}mm",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        vis_image,
        f"Score: {result['fusion_score']:.2f}",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    cv2.imwrite("test_result_visualized.png", vis_image)
    print("\n可视化结果已保存: test_result_visualized.png")

    return result


if __name__ == "__main__":
    test_algorithm()
