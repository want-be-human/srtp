#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试API端点
"""

import requests
import json


def test_yolo_data_api():
    """测试YOLO数据API"""
    print("=== 测试 /api/v1/yolo-data API ===")

    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/yolo-data", timeout=5)
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")

            # 检查数据结构
            if data.get("status") == "success":
                print("\n✓ API返回成功状态")
                yolo_data = data.get("data", {})
                if yolo_data:
                    print(f"检测数据包含以下字段:")
                    for key in yolo_data.keys():
                        print(f"  - {key}")

                    # 检查是否有分数数据
                    if "total_score" in yolo_data:
                        print(f"\n✓ 检测到分数数据: {yolo_data['total_score']}")
                    else:
                        print("\n✗ 未找到分数数据")
                else:
                    print("\n⚠ 检测数据为空")
            else:
                print(f"\n⚠ API状态: {data.get('status')}")
                print(f"消息: {data.get('message', '无消息')}")
        else:
            print(f"错误: {response.text}")

    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到后端服务")
    except requests.exceptions.Timeout:
        print("✗ 请求超时")
    except Exception as e:
        print(f"✗ 测试失败: {e}")


def test_dashboard_api():
    """测试仪表板API"""
    print("\n=== 测试 /api/v1/dashboard/quick-stats API ===")

    try:
        response = requests.get(
            "http://127.0.0.1:8000/api/v1/dashboard/quick-stats", timeout=5
        )
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            print("\n✓ 仪表板API工作正常")
        else:
            print(f"错误: {response.text}")

    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到后端服务")
    except requests.exceptions.Timeout:
        print("✗ 请求超时")
    except Exception as e:
        print(f"✗ 测试失败: {e}")


if __name__ == "__main__":
    test_yolo_data_api()
    test_dashboard_api()
