# -*- coding: utf-8 -*-
"""
焊缝宽度检测模块
基于颜色规律的精确焊缝检测
"""

import cv2
import numpy as np
from typing import Dict


class PreciseWeldDetector:
    """精确焊缝检测器 - 基于颜色规律优化"""

    def __init__(self, debug: bool = False, image_height_cm: float = 15.0):
        self.debug = debug
        self.image_height_cm = image_height_cm  # 图片Y轴实际高度（厘米）

    def enhanced_weld_detection(self, image: np.ndarray) -> Dict:
        """基于亮度梯度特征的增强焊缝检测"""
        height, width = image.shape[:2]

        # 1. 扩大搜索区域（从4%到33%，提高检测稳定性）
        center_y = height // 2
        search_height = height // 3  # 扩大搜索范围，覆盖更多可能区域
        top = max(0, center_y - search_height // 2)
        bottom = min(height, center_y + search_height // 2)

        # 2. 提取中间区域
        center_region = image[top:bottom, :]
        gray = cv2.cvtColor(center_region, cv2.COLOR_RGB2GRAY)

        # 3. 使用亮度梯度特征定位焊缝（向量化操作，速度快）
        region_height = gray.shape[0]

        # 计算每行的平均亮度（向量化，比逐行循环快）
        row_brightness = np.mean(gray, axis=1)

        # 计算亮度梯度（焊缝边缘梯度大）
        row_gradient = np.gradient(row_brightness)

        # 融合特征：亮度 * 梯度绝对值（强调边缘）
        # 焊缝区域特征：亮度高 + 梯度大
        fusion_score = row_brightness * np.abs(row_gradient)

        # 找到最佳焊缝位置
        best_y = np.argmax(fusion_score)
        best_score = fusion_score[best_y]

        # 4. 映射回原图坐标
        actual_y = top + best_y

        # 5. 精确确定焊缝边界（基于银白色特征）
        min_thickness_cm = 0.5
        pixels_per_cm = height / self.image_height_cm
        min_thickness_pixels = int(min_thickness_cm * pixels_per_cm)

        thickness_top = actual_y
        thickness_bottom = actual_y

        # 向上搜索银白色边界
        for dy in range(-12, 0):
            check_y = actual_y + dy
            if 0 <= check_y < height:
                row = cv2.cvtColor(image[check_y : check_y + 1, :], cv2.COLOR_RGB2GRAY)[
                    0
                ]
                bright_ratio = np.sum(row > 120) / width

                if bright_ratio > 0.05:  # 降低到5%银白色
                    thickness_top = check_y
                else:
                    break

        # 向下搜索银白色边界
        for dy in range(1, 13):
            check_y = actual_y + dy
            if 0 <= check_y < height:
                row = cv2.cvtColor(image[check_y : check_y + 1, :], cv2.COLOR_RGB2GRAY)[
                    0
                ]
                bright_ratio = np.sum(row > 120) / width

                if bright_ratio > 0.05:  # 降低到5%银白色
                    thickness_bottom = check_y
                else:
                    break

        thickness = thickness_bottom - thickness_top + 1

        # 6. 确保最小厚度
        if thickness < min_thickness_pixels:
            half_min = min_thickness_pixels // 2
            thickness_top = max(0, actual_y - half_min)
            thickness_bottom = min(height - 1, actual_y + half_min)
            thickness = thickness_bottom - thickness_top + 1

        # 7. 计算物理尺寸
        thickness_cm = float(thickness / pixels_per_cm)
        thickness_mm = float(thickness_cm * 10)

        return {
            "center_y": int(actual_y),
            "top_y": int(thickness_top),
            "bottom_y": int(thickness_bottom),
            "thickness": int(thickness),
            "thickness_cm": thickness_cm,
            "thickness_mm": thickness_mm,
            "pixels_per_cm": float(pixels_per_cm),
            "fusion_score": float(best_score),  # 改为融合分数
            "width": int(width),
            "found": bool(best_score > 0.01),  # 保持检测阈值
        }

    def _get_max_continuous_length(self, row: np.ndarray) -> int:
        """计算最长连续白色像素段"""
        max_length = 0
        current_length = 0

        for pixel in row:
            if pixel == 255:
                current_length += 1
                max_length = max(max_length, current_length)
            else:
                current_length = 0

        return max_length
