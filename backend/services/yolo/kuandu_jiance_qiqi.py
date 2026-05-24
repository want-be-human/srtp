# -*- coding: utf-8 -*-
"""
焊缝宽度检测模块
基于颜色规律的精确焊缝检测
"""

import cv2
import numpy as np
from typing import Dict, Optional, Tuple

# 暗-亮-暗连续性验证：在候选行两侧 [_NEAR..._FAR] 像素带里取均值，
# 焊缝行至少比这两段亮 _MIN_CONTRAST，否则视为孤立亮斑（反光带、飞溅）
_NEAR_OFFSET = 10
_FAR_OFFSET = 20
_MIN_CONTRAST = 25
# 验证失败时最多回退看前 N 个候选
_MAX_CANDIDATES = 5


def _pick_best_row(row_brightness: np.ndarray, fusion_score: np.ndarray) -> int:
    """按 fusion_score 降序找第一个通过暗-亮-暗连续性的行；都没过就退回最亮行。"""
    region_height = len(row_brightness)
    if region_height < 2 * _FAR_OFFSET + 1:
        # 搜索带太窄不足以做两侧采样，直接最亮
        return int(np.argmax(fusion_score))

    candidates = np.argsort(fusion_score)[::-1][:_MAX_CANDIDATES]
    for cand in candidates:
        if cand < _FAR_OFFSET or cand >= region_height - _FAR_OFFSET:
            continue
        center_b = row_brightness[cand]
        above = row_brightness[cand - _FAR_OFFSET : cand - _NEAR_OFFSET].mean()
        below = row_brightness[cand + _NEAR_OFFSET + 1 : cand + _FAR_OFFSET + 1].mean()
        if center_b - above >= _MIN_CONTRAST and center_b - below >= _MIN_CONTRAST:
            return int(cand)
    return int(np.argmax(fusion_score))


class PreciseWeldDetector:

    def __init__(
        self,
        debug: bool = False,
        image_height_cm: float = 15.0,
        pixels_per_mm: Optional[float] = None,
    ):
        self.debug = debug
        # pixels_per_mm 来自摄像头标定，存在时直接用；为 None 时退回
        # "假设画面高度 = image_height_cm" 的旧估算，输出标记 calibrated=False
        self.image_height_cm = image_height_cm
        self.pixels_per_mm = pixels_per_mm

    def enhanced_weld_detection(
        self,
        image: np.ndarray,
        roi_bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict:
        """亮度梯度找焊缝行；roi_bbox 给定时只在该 y 区间里搜，没给就退回中心 1/3。"""
        height, width = image.shape[:2]

        if roi_bbox is not None:
            _, by1, _, by2 = roi_bbox
            top = max(0, int(by1))
            bottom = min(height, int(by2))
            if bottom - top < 3:
                # ROI 太窄就当 ROI 没建立
                roi_bbox = None
        if roi_bbox is None:
            center_y = height // 2
            search_height = height // 3
            top = max(0, center_y - search_height // 2)
            bottom = min(height, center_y + search_height // 2)

        center_region = image[top:bottom, :]
        gray = cv2.cvtColor(center_region, cv2.COLOR_RGB2GRAY)

        # 每行平均亮度 + 梯度强度，融合作为"焊缝可能性"评分
        row_brightness = np.mean(gray, axis=1)
        row_gradient = np.gradient(row_brightness)
        fusion_score = row_brightness * np.abs(row_gradient)

        # 暗-亮-暗连续性筛选，过滤孤立亮斑（反光、飞溅）
        best_y = _pick_best_row(row_brightness, fusion_score)
        best_score = fusion_score[best_y]

        actual_y = top + best_y

        min_thickness_cm = 0.5
        if self.pixels_per_mm is not None:
            pixels_per_cm = self.pixels_per_mm * 10.0
        else:
            pixels_per_cm = height / self.image_height_cm
        min_thickness_pixels = int(min_thickness_cm * pixels_per_cm)

        thickness_top = actual_y
        thickness_bottom = actual_y

        # 5% 银白色门槛：焊缝中线两侧的余高带银亮像素占比通常 > 5%，再低就当背景
        for dy in range(-12, 0):
            check_y = actual_y + dy
            if 0 <= check_y < height:
                row = cv2.cvtColor(image[check_y : check_y + 1, :], cv2.COLOR_RGB2GRAY)[
                    0
                ]
                bright_ratio = np.sum(row > 120) / width

                if bright_ratio > 0.05:
                    thickness_top = check_y
                else:
                    break

        for dy in range(1, 13):
            check_y = actual_y + dy
            if 0 <= check_y < height:
                row = cv2.cvtColor(image[check_y : check_y + 1, :], cv2.COLOR_RGB2GRAY)[
                    0
                ]
                bright_ratio = np.sum(row > 120) / width

                if bright_ratio > 0.05:
                    thickness_bottom = check_y
                else:
                    break

        thickness = thickness_bottom - thickness_top + 1

        # 物理上焊缝再细也得有 0.5cm，宽度上下限收缩到这个最小值，避免边界搜索误判带来异常
        if thickness < min_thickness_pixels:
            half_min = min_thickness_pixels // 2
            thickness_top = max(0, actual_y - half_min)
            thickness_bottom = min(height - 1, actual_y + half_min)
            thickness = thickness_bottom - thickness_top + 1

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
            "fusion_score": float(best_score),
            "width": int(width),
            "found": bool(best_score > 0.01),
            "calibrated": bool(self.pixels_per_mm is not None),
        }

    def _get_max_continuous_length(self, row: np.ndarray) -> int:
        max_length = 0
        current_length = 0

        for pixel in row:
            if pixel == 255:
                current_length += 1
                max_length = max(max_length, current_length)
            else:
                current_length = 0

        return max_length
