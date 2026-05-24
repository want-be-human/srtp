# -*- coding: utf-8 -*-
"""焊缝表面光滑度评分：适中亮度占比 + GLCM 对比度 + 局部方差加权。"""

import cv2
import numpy as np
import os
import json
from typing import Dict

from .weld_roi import suppress_highlight

# GLCM 对比度的归一化上限，超过视为完全粗糙；20 ≈ 8 级量化下接近随机的均值
_GLCM_NORM_CAP = 20.0
# 局部 5×5 方差均值的归一化上限，焊缝表面正常纹理远低于这值
_VARIANCE_NORM_CAP = 200.0


def _glcm_contrast(gray: np.ndarray, levels: int = 8) -> float:
    """水平方向 GLCM 对比度（距离 1），值越大表示像素邻域差异越大、表面越粗糙。"""
    if gray.size < 2 or gray.shape[1] < 2:
        return 0.0
    q = (gray.astype(np.intp) * levels // 256).clip(0, levels - 1)
    # bincount 比 np.add.at 在 2D scatter-add 上快 5-10 倍
    flat = q[:, :-1].ravel() * levels + q[:, 1:].ravel()
    glcm = np.bincount(flat, minlength=levels * levels).astype(np.float64).reshape(levels, levels)
    total = glcm.sum()
    if total == 0:
        return 0.0
    glcm /= total
    i, j = np.indices((levels, levels))
    return float(np.sum((i - j) ** 2 * glcm))


def _local_variance_mean(gray: np.ndarray, ksize: int = 5) -> float:
    """ksize×ksize 局部方差再取均值，越平滑越小。"""
    img = gray.astype(np.float32)
    mean = cv2.boxFilter(img, ddepth=-1, ksize=(ksize, ksize))
    sqr_mean = cv2.boxFilter(img * img, ddepth=-1, ksize=(ksize, ksize))
    var = np.maximum(sqr_mean - mean * mean, 0.0)
    return float(np.mean(var))


class WeldingQualityScorer:

    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)

    def _load_config(self, config_file: str = None) -> Dict:
        default_config = {
            "y_divisions": 4,
            "detection_start_ratio": 0.25,
            "detection_end_ratio": 0.75,
            "brightness_thresholds": {
                "white_min": 200,
                "gray_min": 100,
                "gray_max": 199
            },
            "scoring_weights": {
                "brightness": 0.4,
                "smoothness": 0.4,
                "uniformity": 0.2
            },
            "max_score": 100
        }

        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"警告：无法加载配置文件 {config_file}，使用默认配置。错误：{e}")

        return default_config

    def _get_detection_region(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]

        start_y = int(height * self.config["detection_start_ratio"])
        end_y = int(height * self.config["detection_end_ratio"])

        detection_region = image[start_y:end_y, :]
        return detection_region

    def _analyze_brightness(self, image: np.ndarray) -> Dict[str, float]:
        """先压过曝再分析；除了原有的明暗占比，还输出 GLCM 对比度和局部方差均值。"""
        if image.ndim == 3:
            suppressed = suppress_highlight(image)
            gray = cv2.cvtColor(suppressed, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        total_pixels = gray.size
        th = self.config["brightness_thresholds"]
        white_pixels = np.sum(gray >= th["white_min"])
        gray_pixels = np.sum((gray >= th["gray_min"]) & (gray <= th["gray_max"]))
        black_pixels = np.sum(gray < th["gray_min"])

        return {
            "white_ratio": white_pixels / total_pixels,
            "gray_ratio": gray_pixels / total_pixels,
            "black_ratio": black_pixels / total_pixels,
            "total_pixels": total_pixels,
            "glcm_contrast": _glcm_contrast(gray),
            "local_variance": _local_variance_mean(gray),
        }

    def _calculate_score(self, brightness_analysis: Dict[str, float]) -> float:
        """三项加权：适中亮度占比、低 GLCM 对比度、低局部方差。过曝纯白因 gray_ratio 趋零而被显著压低。"""
        # 适中亮度（[gray_min, gray_max] 区间）的像素占比，过曝时全是白、占比接近 0
        brightness = float(brightness_analysis.get("gray_ratio", 0.0))
        glcm_norm = min(brightness_analysis.get("glcm_contrast", 0.0) / _GLCM_NORM_CAP, 1.0)
        var_norm = min(brightness_analysis.get("local_variance", 0.0) / _VARIANCE_NORM_CAP, 1.0)

        w = self.config["scoring_weights"]
        score = (w["brightness"] * brightness
                 + w["smoothness"] * (1.0 - glcm_norm)
                 + w["uniformity"] * (1.0 - var_norm))
        score *= self.config["max_score"]
        return float(np.clip(score, 0.0, self.config["max_score"]))

    def score_image(self, image_path: str, save_debug: bool = False) -> Dict:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图片: {image_path}")

        detection_region = self._get_detection_region(image)
        brightness_analysis = self._analyze_brightness(detection_region)
        score = self._calculate_score(brightness_analysis)

        result = {
            "image_path": image_path,
            "score": round(score, 2),
            "brightness_analysis": {
                "white_ratio": round(brightness_analysis["white_ratio"], 4),
                "gray_ratio": round(brightness_analysis["gray_ratio"], 4),
                "black_ratio": round(brightness_analysis["black_ratio"], 4)
            },
            "config_used": self.config.copy()
        }

        return result