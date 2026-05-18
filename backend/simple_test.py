#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试API
"""

import requests
import json


def test_api():
    """测试API"""
    print("Testing API...")

    try:
        # 测试仪表板API
        print("\n1. Testing dashboard API...")
        response = requests.get(
            "http://127.0.0.1:8000/api/v1/dashboard/quick-stats", timeout=10
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("Dashboard API OK")
        else:
            print(f"Error: {response.text}")

        # 测试YOLO数据API
        print("\n2. Testing YOLO data API...")
        response = requests.get("http://127.0.0.1:8000/api/v1/yolo-data", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"Error: {response.text}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_api()
