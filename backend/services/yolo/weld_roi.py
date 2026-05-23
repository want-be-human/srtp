# -*- coding: utf-8 -*-
"""焊缝 ROI 引导：HSV 高光抑制后做形态学带状提取，跨帧复用上帧 bbox 收窄搜索带。

过曝的焊渣反光容易被当成焊缝，先把 V 通道压回中亮度；YOLO 在全画面经常乱框，
ROI 外像素衰减、检测后按中心点丢掉外面的框。bbox 和 mask 都缓存在 tracker 上
供后续模块复用。
"""

import cv2
import numpy as np

# V 通道超过此值的像素压到这里；255 - HIGHLIGHT_V_CLIP 大致是允许的过曝余量
HIGHLIGHT_V_CLIP = 220
# 闭运算 kernel：长条形，沿焊缝横向走向把断点连起来
SEAM_MORPH_KERNEL = (21, 3)
# 动态 ROI 膨胀像素：上帧 bbox 向外扩这么多作为本帧的搜索区域
ROI_DILATE_PX = 15
# ROI 外像素的衰减倍数；不置 0 避免人为强边缘干扰 YOLO
ROI_OUT_ATTENUATION = 0.3
_MIN_PIXELS_FOR_PCA = 5

# 在模块加载时建好闭运算 kernel，避免每帧重建
_SEAM_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, SEAM_MORPH_KERNEL)


def suppress_highlight(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hsv[:, :, 2] = np.minimum(hsv[:, :, 2], HIGHLIGHT_V_CLIP)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _extract_seam(bgr, search_region):
    """Otsu 二值化加 21×3 闭运算挑最大连通域；search_region 是 (x0,y0,x1,y1) 子区，
    bbox 返回值始终是全图坐标，找不到焊缝时返回 (None, None, 0)。"""
    h, w = bgr.shape[:2]
    if search_region is None:
        x0, y0, x1, y1 = 0, 0, w, h
    else:
        x0, y0, x1, y1 = search_region
    if x1 <= x0 or y1 <= y0:
        return None, None, 0.0
    crop = bgr[y0:y1, x0:x1]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, _SEAM_KERNEL)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    if n_labels <= 1:
        return None, None, 0.0
    # stats[0] 是背景，从 1 开始找面积最大的连通域
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    bx, by, bw, bh = stats[largest, :4]
    bbox = (int(x0 + bx), int(y0 + by), int(x0 + bx + bw), int(y0 + by + bh))

    seam_local = (labels == largest).astype(np.uint8) * 255
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y0:y0 + seam_local.shape[0], x0:x0 + seam_local.shape[1]] = seam_local

    ys, xs = np.where(seam_local > 0)
    if len(xs) < _MIN_PIXELS_FOR_PCA:
        theta = 0.0
    else:
        coords = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
        coords -= coords.mean(axis=0)
        cov = np.cov(coords.T)
        _, eigvecs = np.linalg.eigh(cov)
        main = eigvecs[:, -1]
        theta = float(np.arctan2(main[1], main[0]))

    return mask, bbox, theta


def _attenuate_outside(bgr, mask):
    if mask is None:
        return bgr
    # convertScaleAbs 在 C 里直接 uint8 缩放，省掉 float 来回两次大块分配
    attenuated = cv2.convertScaleAbs(bgr, alpha=ROI_OUT_ATTENUATION)
    inside = mask > 0
    attenuated[inside] = bgr[inside]
    return attenuated


class WeldRoiTracker:
    """跨帧维护焊缝 ROI，给 YOLO 喂"压过过曝 + 背景衰减"后的帧。"""

    def __init__(self):
        self.last_bbox = None
        self.last_theta = 0.0
        self.last_mask = None

    def process(self, bgr):
        """返回送给 YOLO 的图像，同时把 bbox / mask / theta 缓存到 self 上。"""
        suppressed = suppress_highlight(bgr)

        h, w = suppressed.shape[:2]
        if self.last_bbox is None:
            region = None
        else:
            x1, y1, x2, y2 = self.last_bbox
            region = (
                max(0, x1 - ROI_DILATE_PX),
                max(0, y1 - ROI_DILATE_PX),
                min(w, x2 + ROI_DILATE_PX),
                min(h, y2 + ROI_DILATE_PX),
            )

        mask, bbox, theta = _extract_seam(suppressed, region)
        if bbox is None and region is not None:
            # 局部找不到（可能焊缝移出了上帧 ROI），扩到全图再试一次
            mask, bbox, theta = _extract_seam(suppressed, None)

        if bbox is not None:
            self.last_bbox = bbox
            self.last_theta = theta
            self.last_mask = mask

        return _attenuate_outside(suppressed, mask)

    def should_keep_box(self, box_xyxy):
        """中心点落在当前 ROI bbox 内则保留；ROI 还没建立时一律放行。"""
        if self.last_bbox is None:
            return True
        x1, y1, x2, y2 = box_xyxy
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        rx1, ry1, rx2, ry2 = self.last_bbox
        return rx1 <= cx <= rx2 and ry1 <= cy <= ry2
