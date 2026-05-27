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


def _pick_best_row(row_brightness: np.ndarray, fusion_score: np.ndarray) -> Tuple[int, int]:
    """按 fusion_score 降序找第一个通过暗-亮-暗连续性的行；都没过就退回最亮行。

    返回 (best_y, rejected_count)。rejected_count 是被暗-亮-暗筛掉的候选数，
    透传到 MJPEG 角标可视化，方便观察拟态过滤的实际工作量。
    """
    region_height = len(row_brightness)
    if region_height < 2 * _FAR_OFFSET + 1:
        # 搜索带太窄不足以做两侧采样，直接最亮
        return int(np.argmax(fusion_score)), 0

    candidates = np.argsort(fusion_score)[::-1][:_MAX_CANDIDATES]
    rejected = 0
    for cand in candidates:
        if cand < _FAR_OFFSET or cand >= region_height - _FAR_OFFSET:
            rejected += 1
            continue
        center_b = row_brightness[cand]
        above = row_brightness[cand - _FAR_OFFSET : cand - _NEAR_OFFSET].mean()
        below = row_brightness[cand + _NEAR_OFFSET + 1 : cand + _FAR_OFFSET + 1].mean()
        if center_b - above >= _MIN_CONTRAST and center_b - below >= _MIN_CONTRAST:
            return int(cand), rejected
        rejected += 1
    return int(np.argmax(fusion_score)), rejected


# 未标定兜底时的假设画面高度（cm），仅用于让宽度模块仍能跑出一个数；
# 任何依赖 mm 数值的判定都必须先看返回 dict 里的 calibrated 标志。
FALLBACK_IMAGE_HEIGHT_CM = 15.0


# 逐列采样找焊缝参数：沿 X 轴每 _COL_STEP 像素取一列，每列独立用 FWHM 找上下边界。
# 比"找一行最亮"鲁棒得多：单列噪声被多列平均抹掉，倾斜 / 弯曲焊缝也能贴合走向。
_COL_STEP = 30
_FWHM_RATIO = 0.5            # 半高全宽：peak * 0.5 作为上下边界阈值
_MIN_PEAK_BRIGHTNESS = 50    # 列内峰值太暗就当这列没焊缝；放宽到 50 兼容暗淡焊缝
_MIN_VALID_COLUMNS = 4       # 至少 4 列收敛才算找到焊缝；放宽到 4 兼容焊缝短的情况
_OUTLIER_CENTER_PX_RATIO = 0.04   # 列中心 y 偏离中位数超过帧高 * 这个比例剔除
_OUTLIER_THICK_RATIO = 0.6   # 列厚度偏离中位数超过这个比例剔除
# 焊缝粗定位的行均值平滑窗口：避免列 argmax 被画面其他亮区（充电宝、反光带）干扰。
# 整图行均值 → 平滑 → argmax 得到焊缝大致 Y 中心，然后列采样只在中心 ±band_radius 范围内
_ROW_SMOOTH_WIN = 31
# 默认搜索带半径（pixels_per_mm 可用时按 max_weld_mm * pixels_per_mm 计算覆盖物理厚度）
_DEFAULT_BAND_HEIGHT_RATIO = 0.15  # 帧高 15% 作 fallback 半径


def detect_along_columns(
    image_rgb: np.ndarray,
    pixels_per_mm: Optional[float] = None,
    image_height_cm: float = FALLBACK_IMAGE_HEIGHT_CM,
    col_step: int = _COL_STEP,
) -> Dict:
    """逐列采样 + FWHM 找焊缝，返回三组曲线点（中心 / 上界 / 下界）和平均宽度。

    跟原 enhanced_weld_detection 的差异：
    - 原算法找一行最亮，假设焊缝水平，倾斜 / 弯曲焊缝会偏
    - 原算法上下扩展靠绝对亮度阈值（120），同样焊件不同光照下不稳
    - 新算法每列独立找峰值 + FWHM（相对阈值），抗光照、抗倾斜、给出焊缝走向

    粗定位：整图行均值平滑后 argmax 得焊缝大致 Y，列采样只在中心 ±band_radius 范围
    内做，避免画面里其他亮区（充电宝、塑料反光带）把列 argmax 拽走。
    """
    height, width = image_rgb.shape[:2]
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)

    # Step 1: 焊缝行粗定位。整行平均亮度后用 _ROW_SMOOTH_WIN 平滑窗口去 hotspot
    row_mean = gray.mean(axis=1).astype(np.float32)
    win = min(_ROW_SMOOTH_WIN, max(3, height // 50))
    if win % 2 == 0:
        win += 1
    kernel = np.ones(win, dtype=np.float32) / win
    row_smoothed = np.convolve(row_mean, kernel, mode="same")
    center_y_global = int(np.argmax(row_smoothed))

    # Step 2: 限定搜索带半径。标定可用按物理上限（22mm 留 2× 余量）；否则按帧高比例
    if pixels_per_mm:
        band_radius = max(50, int(22.0 * pixels_per_mm))
    else:
        band_radius = max(50, int(height * _DEFAULT_BAND_HEIGHT_RATIO))

    band_top = max(0, center_y_global - band_radius)
    band_bot = min(height, center_y_global + band_radius + 1)

    # Step 3: 在搜索带内做列 FWHM
    columns_raw = []  # 每个元素 (x, center_y, top_y, bottom_y) - 全图坐标
    sample_xs = list(range(col_step, max(col_step + 1, width - col_step), col_step))
    skipped_dim = 0

    for x in sample_xs:
        col = gray[band_top:band_bot, x]
        if col.size < 5:
            continue
        peak_y_local = int(np.argmax(col))
        peak_val = int(col[peak_y_local])

        if peak_val < _MIN_PEAK_BRIGHTNESS:
            skipped_dim += 1
            continue

        half = peak_val * _FWHM_RATIO
        top_l = peak_y_local
        while top_l > 0 and col[top_l - 1] >= half:
            top_l -= 1
        bot_l = peak_y_local
        while bot_l < col.size - 1 and col[bot_l + 1] >= half:
            bot_l += 1

        # 转回全图坐标
        columns_raw.append((
            x,
            band_top + peak_y_local,
            band_top + top_l,
            band_top + bot_l,
        ))

    band_meta = {
        "band_center_y": center_y_global,
        "band_top": band_top,
        "band_bot": band_bot,
        "skipped_dim_cols": skipped_dim,
        "sampled_cols": len(sample_xs),
    }

    if len(columns_raw) < _MIN_VALID_COLUMNS:
        # 列收敛不足：用户能在 OSD 看到 band 框 + 失败提示，知道粗定位在哪
        return {
            "found": False,
            "columns": [],
            "width_mm": 0.0,
            "thickness_px": 0.0,
            "raw_count": len(columns_raw),
            "valid_count": 0,
            "calibrated": bool(pixels_per_mm is not None),
            "frame_w": int(width),
            "frame_h": int(height),
            "fail_reason": f"列峰值不够亮（{skipped_dim} 列被暗淡剔除）",
            **band_meta,
        }

    # 离群剔除：相对中位数判定，对绝对亮度差异免疫
    centers_arr = np.array([c[1] for c in columns_raw])
    thick_arr = np.array([c[3] - c[2] + 1 for c in columns_raw])
    median_center = float(np.median(centers_arr))
    median_thick = float(np.median(thick_arr))

    # 中心偏离阈值按帧高比例算，不写死像素，适应各种分辨率
    center_tol_px = max(30, int(height * _OUTLIER_CENTER_PX_RATIO))

    columns_valid = [
        c for c in columns_raw
        if abs(c[1] - median_center) <= center_tol_px
        and abs((c[3] - c[2] + 1) - median_thick) <= median_thick * _OUTLIER_THICK_RATIO
    ]

    if len(columns_valid) < _MIN_VALID_COLUMNS:
        # 中位数过滤后没剩多少有效列，说明焊缝识别不稳，放弃
        return {
            "found": False,
            "columns": [],
            "width_mm": 0.0,
            "thickness_px": 0.0,
            "raw_count": len(columns_raw),
            "valid_count": len(columns_valid),
            "calibrated": bool(pixels_per_mm is not None),
            "frame_w": int(width),
            "frame_h": int(height),
            "fail_reason": f"列收敛不稳（{len(columns_raw)}/{len(sample_xs)} 候选, 离群后剩 {len(columns_valid)}）",
            **band_meta,
        }

    avg_thick_px = float(np.mean([c[3] - c[2] + 1 for c in columns_valid]))

    if pixels_per_mm:
        width_mm = avg_thick_px / float(pixels_per_mm)
    else:
        pixels_per_cm = height / image_height_cm
        width_mm = avg_thick_px / pixels_per_cm * 10.0

    return {
        "found": True,
        "columns": columns_valid,  # [(x, center, top, bot), ...]
        "width_mm": float(width_mm),
        "thickness_px": avg_thick_px,
        "raw_count": len(columns_raw),
        "valid_count": len(columns_valid),
        "calibrated": bool(pixels_per_mm is not None),
        "frame_w": int(width),
        "frame_h": int(height),
        **band_meta,
    }


class PreciseWeldDetector:

    def __init__(
        self,
        debug: bool = False,
        image_height_cm: Optional[float] = None,
        pixels_per_mm: Optional[float] = None,
    ):
        self.debug = debug
        # pixels_per_mm 来自摄像头标定，存在时直接用；为 None 时退回
        # "假设画面高度 = image_height_cm" 的旧估算，输出标记 calibrated=False
        self.image_height_cm = image_height_cm if image_height_cm is not None else FALLBACK_IMAGE_HEIGHT_CM
        self.pixels_per_mm = pixels_per_mm
        if pixels_per_mm is None:
            print(
                f"[WARN] PreciseWeldDetector 未标定：假设画面高度 {self.image_height_cm:.1f}cm 估算 mm，"
                "结果带 calibrated=False；请走 /calibration 标定后才能当真实测量值用"
            )

    def detect_columns(self, image_rgb: np.ndarray) -> Dict:
        """逐列采样 + FWHM 找焊缝（推荐路径）。

        包装顶层 detect_along_columns，自动喂入实例的 pixels_per_mm 和 image_height_cm。
        相比 enhanced_weld_detection：
        - 给出沿焊缝的曲线（中心 / 上下边界各一条），抗倾斜
        - 用相对阈值（FWHM）替代绝对亮度，抗光照
        - 不依赖 ROI tracker，免漂移
        """
        return detect_along_columns(
            image_rgb,
            pixels_per_mm=self.pixels_per_mm,
            image_height_cm=self.image_height_cm,
        )

    def enhanced_weld_detection(
        self,
        image: np.ndarray,
        roi_bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict:
        """[legacy] 亮度梯度找焊缝行；roi_bbox 给定时只在该 y 区间里搜，没给就退回中心 1/3。

        保留作 fallback：新的 detect_columns 在某些图上不收敛时仍能跑出一个数。
        """
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
        best_y, rejected_count = _pick_best_row(row_brightness, fusion_score)
        best_score = fusion_score[best_y]

        actual_y = top + best_y

        min_thickness_cm = 0.5
        if self.pixels_per_mm is not None:
            pixels_per_cm = self.pixels_per_mm * 10.0
        else:
            pixels_per_cm = height / self.image_height_cm
        min_thickness_pixels = int(min_thickness_cm * pixels_per_cm)

        # 搜索半径按真实物理宽度上限算，避免硬编码 ±12 像素把宽度上限锁死：
        # 之前死磕 ±12，遇到标定 pixels_per_mm≈5 时无论真实多宽都被夹在 5mm 以内。
        # 真实焊缝 1-15mm，留 1.5 倍裕量按 22mm 上限去找两侧暗带。
        max_half_search_mm = 22.0 / 2.0
        search_radius_px = max(12, int(max_half_search_mm * pixels_per_cm / 10.0))

        thickness_top = actual_y
        thickness_bottom = actual_y

        # 5% 银白色门槛：焊缝中线两侧的余高带银亮像素占比通常 > 5%，再低就当背景
        for dy in range(-search_radius_px, 0):
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

        for dy in range(1, search_radius_px + 1):
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
            "rejected_count": int(rejected_count),
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
