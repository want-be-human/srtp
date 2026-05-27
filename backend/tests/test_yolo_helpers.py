"""YOLO 服务层里不依赖 best.pt 的纯算法测试。

只覆盖：
1. IntegratedWeldDetector._load_config：缺省 / 用户 JSON 合并；
2. PreciseWeldDetector.enhanced_weld_detection：随机图不崩、返回结构完整；
3. WeldingQualityScorer._analyze_brightness + _calculate_score：过曝白板被压分（修过的 bug），
   平滑灰板拿高分；
4. WeldRoiTracker：合成图上能正确锁定主焊缝带、忽略角落反光。

best.pt 加载在 _init_modules 里，直接 instantiate IntegratedWeldDetector 会慢，
因此用 unbound 方法 cls._load_config(None, ...) 单独测，避免初始化整个模型。
"""

import json

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from services.yolo import (
    IntegratedWeldDetector,
    PreciseWeldDetector,
    WeldingQualityScorer,
)
from services.yolo.weld_roi import WeldRoiTracker


class TestIntegratedConfig:
    def test_default_config_when_file_missing(self, tmp_path):
        # 走 unbound 方法绕过 __init__ 里的 YOLO best.pt 加载
        cfg = IntegratedWeldDetector._load_config(None, str(tmp_path / "nope.json"))
        assert cfg["confidence_threshold"] == 0.3
        assert cfg["iou_threshold"] == 0.45
        assert "scoring_weights" in cfg

    def test_default_config_when_path_is_none(self):
        cfg = IntegratedWeldDetector._load_config(None, None)
        assert cfg["yolo_model_path"] == "models/best.pt"

    def test_user_config_merges(self, tmp_path):
        # 用户文件里覆盖 confidence_threshold 应该真的覆盖
        user_file = tmp_path / "user.json"
        user_file.write_text(json.dumps({"confidence_threshold": 0.7}), encoding="utf-8")
        cfg = IntegratedWeldDetector._load_config(None, str(user_file))
        assert cfg["confidence_threshold"] == 0.7
        # 没被用户覆盖的字段保留 default
        assert cfg["iou_threshold"] == 0.45


class TestPreciseWeldDetection:
    def test_random_image_does_not_crash(self):
        # 随机噪声图不该让算法异常，返回 dict 必带这些键
        det = PreciseWeldDetector(pixels_per_mm=2.0)
        rng = np.random.default_rng(42)
        img = rng.integers(0, 255, size=(480, 640, 3), dtype=np.uint8)
        out = det.enhanced_weld_detection(img)
        for key in ("center_y", "top_y", "bottom_y", "thickness", "thickness_mm",
                    "pixels_per_cm", "width", "found", "calibrated"):
            assert key in out
        assert out["calibrated"] is True
        assert out["width"] == 640

    def test_uncalibrated_marks_calibrated_false(self):
        det = PreciseWeldDetector(pixels_per_mm=None)
        img = np.full((480, 640, 3), 100, np.uint8)
        out = det.enhanced_weld_detection(img)
        assert out["calibrated"] is False


class TestBrightnessScoring:
    def test_overexposed_white_is_not_perfect(self):
        # 全白过曝板：曾经会拿 100 分，修过 bug 后 gray_ratio=0 拉低分（应远低于 100）
        scorer = WeldingQualityScorer()
        white_bgr = cv2.cvtColor(np.full((100, 200), 255, np.uint8), cv2.COLOR_GRAY2BGR)
        analysis = scorer._analyze_brightness(white_bgr)
        assert analysis["white_ratio"] == pytest.approx(1.0)
        assert analysis["gray_ratio"] == pytest.approx(0.0)
        score = scorer._calculate_score(analysis)
        # 严格断言：白板不能再拿到 100 分；按现行权重大约 60 上下
        assert score < 80

    def test_smooth_gray_gets_high_score(self):
        # 平滑灰板（150 ± 10）：gray_ratio 接近 1、纹理小，应拿高分
        scorer = WeldingQualityScorer()
        rng = np.random.default_rng(0)
        noise = rng.integers(-10, 10, size=(100, 200), dtype=np.int16)
        gray = np.clip(150 + noise, 0, 255).astype(np.uint8)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        analysis = scorer._analyze_brightness(gray_bgr)
        assert analysis["gray_ratio"] >= 0.95
        score = scorer._calculate_score(analysis)
        assert score >= 80


class TestWeldRoiTracker:
    def test_finds_main_stripe_ignores_corner_glare(self):
        # 合成图：中间一条横向亮条纹（主焊缝） + 角落一个反光小斑块
        img = np.full((480, 640, 3), 30, np.uint8)
        img[220:260, 50:590] = 230   # 主焊缝带（面积 40 × 540 = 21600）
        img[10:60, 580:630] = 255    # 角落反光（面积 50 × 50 = 2500）

        tracker = WeldRoiTracker()
        out = tracker.process(img)

        assert tracker.last_bbox is not None
        x1, y1, x2, y2 = tracker.last_bbox
        # 主焊缝中心 y=240；锁定的 bbox y 区间应该跨过它
        assert y1 <= 240 <= y2
        # x 跨度应大于角落反光的 50 像素宽
        assert (x2 - x1) > 100
        assert out.shape == img.shape

    def test_should_keep_box_inside_roi(self):
        tracker = WeldRoiTracker()
        # ROI 未建立时一律放行
        assert tracker.should_keep_box([100, 100, 200, 200]) is True

        # 手动设置 ROI 后，中心点在 ROI 里的保留，外面的丢
        tracker.last_bbox = (100, 100, 300, 200)
        assert tracker.should_keep_box([150, 120, 200, 180]) is True  # 中心 (175, 150) ∈ ROI
        assert tracker.should_keep_box([400, 400, 500, 500]) is False  # 在 ROI 外
