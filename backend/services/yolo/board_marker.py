"""焊板粉笔圆点标记识别。

教学场景里依次放 3 块焊板录视频，每块焊板右下角用粉笔画 1/2/3 个白色圆点：
- HSV 找白色像素（粉笔 saturation 低、value 高）
- 开运算去噪 + 闭运算合并粉笔笔迹
- 连通组件计数 + 面积 / 圆形度过滤
- 数量 = 焊板编号

ROI 默认限在画面右下 40% 子区域，避免被焊缝飞溅 / 油污 / 反光误数。
"""

from collections import deque
from typing import Optional, Tuple

import cv2
import numpy as np


# 白色 HSV 阈值
_WHITE_HSV_LO = (0, 0, 200)
_WHITE_HSV_HI = (180, 50, 255)

# 形态学：开运算去小噪点，闭运算把分散粉笔点合并成一团
_OPEN_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
_CLOSE_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

# 连通块面积范围按 ROI 像素面积比例：太小 = 噪点；太大 = 大块反光
_MIN_BLOB_AREA_RATIO = 0.0008
_MAX_BLOB_AREA_RATIO = 0.05

# 圆形度阈值：bbox 宽高比 + 填充率，过滤长条形粉笔笔触
_MIN_BBOX_RATIO = 0.5
_MIN_FILL = 0.4

# 默认 ROI：画面右下 40% 区域 (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
DEFAULT_ROI: Tuple[float, float, float, float] = (0.6, 0.6, 1.0, 1.0)


def detect_board_id(
    bgr_frame: np.ndarray,
    roi_ratio: Tuple[float, float, float, float] = DEFAULT_ROI,
) -> Optional[int]:
    """识别焊板编号（1/2/3）；未识别 / 数量异常 / ROI 太小返回 None。"""
    if bgr_frame is None or bgr_frame.size == 0:
        return None

    h, w = bgr_frame.shape[:2]
    x1 = int(w * roi_ratio[0])
    y1 = int(h * roi_ratio[1])
    x2 = int(w * roi_ratio[2])
    y2 = int(h * roi_ratio[3])
    if x2 - x1 < 30 or y2 - y1 < 30:
        return None
    roi = bgr_frame[y1:y2, x1:x2]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, _WHITE_HSV_LO, _WHITE_HSV_HI)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _OPEN_KERNEL)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _CLOSE_KERNEL)

    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    roi_area = (x2 - x1) * (y2 - y1)
    min_area = int(roi_area * _MIN_BLOB_AREA_RATIO)
    max_area = int(roi_area * _MAX_BLOB_AREA_RATIO)

    valid_count = 0
    for i in range(1, n_labels):  # 0 是背景
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < max(20, min_area) or area > max_area:
            continue
        bbox_w = int(stats[i, cv2.CC_STAT_WIDTH])
        bbox_h = int(stats[i, cv2.CC_STAT_HEIGHT])
        if bbox_w == 0 or bbox_h == 0:
            continue
        # 长宽比 + 填充率，过滤长条 / 不规则形状（粉笔笔触常为长条）
        wh_ratio = min(bbox_w, bbox_h) / max(bbox_w, bbox_h)
        fill = area / (bbox_w * bbox_h)
        if wh_ratio < _MIN_BBOX_RATIO or fill < _MIN_FILL:
            continue
        valid_count += 1

    if valid_count in (1, 2, 3):
        return valid_count
    return None


def get_roi_abs_bbox(
    frame_shape: Tuple[int, int],
    roi_ratio: Tuple[float, float, float, float] = DEFAULT_ROI,
) -> Tuple[int, int, int, int]:
    """ROI 比例转绝对像素 bbox，供 OSD 可视化用。"""
    h, w = frame_shape[:2]
    return (
        int(w * roi_ratio[0]),
        int(h * roi_ratio[1]),
        int(w * roi_ratio[2]),
        int(h * roi_ratio[3]),
    )


class BoardIdStabilizer:
    """多帧投票稳定器：连续 stable_frames 帧识别到同一 ID 才切换 preset。
    单帧噪声（粉笔被光线晃眼 / 摄像头抖动）不会让 preset 频繁跳变。
    """

    def __init__(self, stable_frames: int = 5):
        self.stable_frames = max(1, stable_frames)
        self.history: deque = deque(maxlen=self.stable_frames)
        self.current_id: Optional[int] = None

    def update(self, raw_id: Optional[int]) -> Optional[int]:
        """送入当前帧识别结果，返回稳定 ID（可能跟上一帧一样）。"""
        self.history.append(raw_id)
        if len(self.history) < self.stable_frames:
            return self.current_id

        recent = list(self.history)
        first = recent[0]
        if first is not None and all(r == first for r in recent):
            # 连续 N 帧同一 ID（非 None）→ 切换
            self.current_id = first
        elif all(r is None for r in recent):
            # 连续 N 帧都没识别到 → 清除（焊板移走 / 标记被遮挡）
            self.current_id = None
        # 其他情况（混合）保持上一次 current_id 不动
        return self.current_id

    def reset(self):
        self.history.clear()
        self.current_id = None
