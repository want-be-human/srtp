#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据类型转换
"""

import json
import numpy as np
from services.yolo.kuandu_jiance_qiqi import PreciseWeldDetector
from services.yolo.zonghe_hanjie_zhiliang_jiance_xitong import IntegratedWeldDetector


def test_kuandu_types():
    """测试宽度检测算法的返回值类型"""
    print("=== 测试宽度检测算法返回值类型 ===")
    detector = PreciseWeldDetector()
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    result = detector.enhanced_weld_detection(test_image)

    print("原始返回值类型:")
    for key, value in result.items():
        print(f"  {key}: {type(value)} - {value}")

    # 测试JSON序列化
    try:
        json_str = json.dumps(result)
        print("\n✓ JSON序列化成功")
        print(f"JSON长度: {len(json_str)} 字符")
    except Exception as e:
        print(f"\n✗ JSON序列化失败: {e}")


def test_integrated_types():
    """测试综合检测系统的返回值类型"""
    print("\n=== 测试综合检测系统返回值类型 ===")

    # 创建检测器
    detector = IntegratedWeldDetector()

    # 创建测试图像
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # 测试各个检测方法
    print("1. 测试光滑度检测:")
    smoothness_result = detector.detect_smoothness(test_image)
    print(f"  返回值类型: {type(smoothness_result)}")

    print("\n2. 测试宽度检测:")
    width_result = detector.detect_width(test_image)
    print(f"  返回值类型: {type(width_result)}")

    print("\n3. 测试缺陷检测:")
    defect_result = detector.detect_defects(test_image)
    print(f"  返回值类型: {type(defect_result)}")

    # 测试综合处理
    print("\n4. 测试综合处理:")
    integrated_result = detector.process_frame(test_image)
    print(f"  返回值类型: {type(integrated_result)}")

    # 测试JSON序列化
    try:
        json_str = json.dumps(integrated_result)
        print("\n✓ 综合结果JSON序列化成功")
        print(f"JSON长度: {len(json_str)} 字符")
    except Exception as e:
        print(f"\n✗ 综合结果JSON序列化失败: {e}")
        print("错误详情:")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_kuandu_types()
    test_integrated_types()
