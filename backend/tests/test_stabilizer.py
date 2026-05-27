"""DetectionStabilizer + IoU + bbox 归一化的单元测试。

实时检测路径靠这三件保证前端拿到的是稳定结果：
1. _box_iou 在重叠/不重叠/退化框上行为正确；
2. DetectionStabilizer 需要连续多帧才确认目标，单帧噪声丢掉；
3. EMA 平滑让分数不会一帧跳到 0；
4. _normalize_bboxes 丢弃良品 / 越界 / 退化框，并把像素坐标变成 [0,1]。

直接 import yolo_realtime 会拖一堆 cv2 / numpy / 检测器全局初始化，但不会启动线程，
模块层 OK 就能拿到 _box_iou、DetectionStabilizer、_normalize_bboxes 三个纯函数对象。
"""

import pytest

from api.yolo_realtime import (
    DetectionStabilizer,
    STABILIZER_CONFIRM,
    STABILIZER_EMA_ALPHA,
    STABILIZER_TRACK_TTL,
    _box_iou,
    _normalize_bboxes,
)


class TestBoxIoU:
    def test_identical_boxes(self):
        assert _box_iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)

    def test_no_overlap(self):
        assert _box_iou([0, 0, 5, 5], [10, 10, 20, 20]) == 0.0

    def test_half_overlap_manual(self):
        # 两框面积各 100，交集 [5,5,10,10] = 25，并集 100+100-25 = 175，IoU = 25/175
        iou = _box_iou([0, 0, 10, 10], [5, 5, 15, 15])
        assert iou == pytest.approx(25.0 / 175.0)

    @pytest.mark.parametrize("box_b", [
        [5, 5, 5, 15],   # w = 0
        [5, 5, 15, 5],   # h = 0
        [5, 5, 5, 5],    # 完全退化点
    ])
    def test_degenerate_returns_zero(self, box_b):
        assert _box_iou([0, 0, 10, 10], box_b) == 0.0


def _det(cls_name, box, conf=0.9):
    """构造一个 stabilizer.update 接受的最小 detection dict。"""
    return {"class_name": cls_name, "box": box, "confidence": conf}


class TestDetectionStabilizerConfirmation:
    def test_first_two_frames_no_confirmation(self):
        # 默认 STABILIZER_CONFIRM=3，前两帧塞同一类都不应输出 confirmed
        s = DetectionStabilizer()
        for _ in range(STABILIZER_CONFIRM - 1):
            confirmed, _ = s.update([_det("Crack", [0, 0, 10, 10])], {"total_score": 80})
            assert confirmed == []

    def test_third_frame_confirms(self):
        # 第三帧时 track 在窗口内累计 3 次，应输出 confirmed
        s = DetectionStabilizer()
        for _ in range(STABILIZER_CONFIRM):
            confirmed, _ = s.update([_det("Crack", [0, 0, 10, 10])], {"total_score": 80})
        assert len(confirmed) == 1
        assert confirmed[0]["class_name"] == "Crack"

    def test_single_frame_noise_never_confirms(self):
        # 单帧出现一次 Porosity，之后再没出现 → 永远不应被确认
        s = DetectionStabilizer()
        confirmed, _ = s.update([_det("Porosity", [50, 50, 80, 80])], {"total_score": 80})
        assert confirmed == []
        # 再喂 5 帧空检测，Porosity track 应该被 TTL 清掉，仍不确认
        for _ in range(5):
            confirmed, _ = s.update([], {"total_score": 80})
            assert confirmed == []


class TestDetectionStabilizerEMA:
    def test_first_frame_no_smoothing(self):
        # 第一帧 smoothed 取原值
        s = DetectionStabilizer()
        _, scores = s.update([], {"total_score": 100})
        assert scores["total_score"] == 100.0

    def test_second_frame_ema(self):
        # 第二帧 raw=0：smoothed = 0.4*0 + 0.6*100 = 60，不能直接跳到 0
        s = DetectionStabilizer()
        s.update([], {"total_score": 100})
        _, scores = s.update([], {"total_score": 0})
        expected = STABILIZER_EMA_ALPHA * 0 + (1 - STABILIZER_EMA_ALPHA) * 100
        assert scores["total_score"] == pytest.approx(expected)

    def test_repeated_same_value_converges(self):
        # 连续塞同一个值，smoothed 应该收敛到该值附近
        s = DetectionStabilizer()
        for _ in range(20):
            _, scores = s.update([], {"total_score": 75})
        assert scores["total_score"] == pytest.approx(75.0, abs=0.1)


class TestDetectionStabilizerTTL:
    def test_track_dropped_after_ttl(self):
        # 第 1 帧建 track，连续 TTL+1 帧不出现 → 应被清掉，再喂一帧也不会瞬间 confirm
        s = DetectionStabilizer()
        s.update([_det("Crack", [0, 0, 10, 10])], {"total_score": 80})
        for _ in range(STABILIZER_TRACK_TTL + 1):
            s.update([], {"total_score": 80})
        assert s.tracks == []


class TestNormalizeBboxes:
    def test_good_weld_filtered(self):
        # 良品框（class_name='Good Weld' / class_name_cn='良好焊缝'）都该被丢弃
        out = _normalize_bboxes([
            {"class_name": "Good Weld", "box": [0, 0, 100, 100], "confidence": 0.9},
            {"class_name_cn": "良好焊缝", "box": [10, 10, 50, 50], "confidence": 0.9},
        ], img_w=640, img_h=480)
        assert out == []

    def test_out_of_bounds_filtered(self):
        # x2 > img_w 的越界框应该被丢
        out = _normalize_bboxes([
            {"class_name": "Crack", "box": [0, 0, 700, 100], "confidence": 0.9},
        ], img_w=640, img_h=480)
        assert out == []

    def test_degenerate_filtered(self):
        # w < 1 / h < 1 的退化框应该被丢
        out = _normalize_bboxes([
            {"class_name": "Crack", "box": [10, 10, 10.5, 30], "confidence": 0.9},
        ], img_w=640, img_h=480)
        assert out == []

    def test_valid_box_normalized(self):
        # box [160, 120, 320, 240] 在 640x480 上 → cx=0.375, cy=0.375, w=0.25, h=0.25
        out = _normalize_bboxes([
            {"class_name": "Crack", "class_name_cn": "裂纹",
             "box": [160, 120, 320, 240], "confidence": 0.82},
        ], img_w=640, img_h=480)
        assert len(out) == 1
        b = out[0]
        assert b["label"] == "Crack"
        assert b["label_cn"] == "裂纹"
        assert b["cx"] == pytest.approx(0.375)
        assert b["cy"] == pytest.approx(0.375)
        assert b["w"] == pytest.approx(0.25)
        assert b["h"] == pytest.approx(0.25)
        assert b["conf"] == 0.82

    def test_zero_img_size_returns_empty(self):
        # 防御性：img_w/h <= 0 直接返回空，不要除零
        assert _normalize_bboxes([{"class_name": "Crack", "box": [0, 0, 10, 10]}], 0, 480) == []
