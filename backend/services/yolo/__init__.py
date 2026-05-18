# -*- coding: utf-8 -*-
"""
YOLO检测服务模块
包含焊缝质量综合检测系统的所有组件
"""

from .zonghe_hanjie_zhiliang_jiance_xitong import IntegratedWeldDetector
from .guanghuadu_jiance_qiqi import WeldingQualityScorer
from .kuandu_jiance_qiqi import PreciseWeldDetector

__all__ = ['IntegratedWeldDetector', 'WeldingQualityScorer', 'PreciseWeldDetector']
