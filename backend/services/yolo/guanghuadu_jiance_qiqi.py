# -*- coding: utf-8 -*-
"""
光滑度检测模块
通过分析焊接钢板图片的明暗度来评估焊缝质量
"""

import cv2
import numpy as np
import os
import json
from typing import Dict

class WeldingQualityScorer:
    """焊缝质量评分器"""

    def __init__(self, config_file: str = None):
        """初始化评分器"""
        self.config = self._load_config(config_file)

    def _load_config(self, config_file: str = None) -> Dict:
        """加载配置参数"""
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
                "white_weight": 1.0,
                "gray_weight": 0.5,
                "black_weight": 0.0
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
        """获取检测区域（焊缝所在区域）"""
        height, width = image.shape[:2]

        start_y = int(height * self.config["detection_start_ratio"])
        end_y = int(height * self.config["detection_end_ratio"])

        detection_region = image[start_y:end_y, :]
        return detection_region

    def _analyze_brightness(self, image: np.ndarray) -> Dict[str, float]:
        """分析图像明暗度"""
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        total_pixels = gray.size

        # 根据阈值分类像素
        white_pixels = np.sum(gray >= self.config["brightness_thresholds"]["white_min"])
        gray_pixels = np.sum((gray >= self.config["brightness_thresholds"]["gray_min"]) &
                           (gray <= self.config["brightness_thresholds"]["gray_max"]))
        black_pixels = np.sum(gray < self.config["brightness_thresholds"]["gray_min"])

        # 计算占比
        white_ratio = white_pixels / total_pixels
        gray_ratio = gray_pixels / total_pixels
        black_ratio = black_pixels / total_pixels

        return {
            "white_ratio": white_ratio,
            "gray_ratio": gray_ratio,
            "black_ratio": black_ratio,
            "total_pixels": total_pixels
        }

    def _calculate_score(self, brightness_analysis: Dict[str, float]) -> float:
        """计算焊缝质量得分"""
        weights = self.config["scoring_weights"]

        weighted_score = (
            brightness_analysis["white_ratio"] * weights["white_weight"] +
            brightness_analysis["gray_ratio"] * weights["gray_weight"] +
            brightness_analysis["black_ratio"] * weights["black_weight"]
        )

        score = weighted_score * self.config["max_score"]
        return min(max(score, 0), self.config["max_score"])

    def score_image(self, image_path: str, save_debug: bool = False) -> Dict:
        """对单张图片进行评分"""
        # 读取图片
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图片: {image_path}")

        # 获取检测区域
        detection_region = self._get_detection_region(image)

        # 分析明暗度
        brightness_analysis = self._analyze_brightness(detection_region)

        # 计算得分
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