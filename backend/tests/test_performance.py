"""性能基线测试 — 把第四章"运行速度"维度的关键数字钉住。

这些用例标 @pytest.mark.slow，CI 默认跳过；本地一次性跑 `pytest -m slow` 验证。

关键基线（来自 docs/算法升级汇总.md 的实测值）：
- DetectionStabilizer 单次 update < 5 ms
- 1D-CNN forecast 单次推理 < 50 ms（CPU，文档声称 < 10 ms 我留余量）
- _aggregate_radar 200 条记录 < 50 ms
- box_iou 100k 次调用 < 200 ms
"""

import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))


def _bench(fn, *, iterations: int, warmup: int = 1) -> dict:
    """跑 iterations 次取平均/p50/p95（ms）。"""
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "avg_ms": statistics.mean(samples),
        "p50_ms": statistics.median(samples),
        "p95_ms": sorted(samples)[int(0.95 * len(samples))],
        "max_ms": max(samples),
        "n": iterations,
    }


@pytest.mark.slow
class TestStabilizerLatency:
    def test_stabilizer_update_under_5ms(self):
        from api.yolo_realtime import DetectionStabilizer

        stab = DetectionStabilizer()
        detections = [
            {"box": [10 + i, 20, 100 + i, 90], "class_name": "Crack", "confidence": 0.7}
            for i in range(8)  # 8 个并存目标，比典型场景更复杂
        ]
        scores = {"total_score": 80.0, "smoothness_score": 80.0,
                  "width_score": 80.0, "defect_score": 80.0}

        def _once():
            stab.update(detections, scores)

        result = _bench(_once, iterations=500)
        print(f"\n[Stabilizer] avg={result['avg_ms']:.3f} ms, p95={result['p95_ms']:.3f} ms")
        # 文档声称单帧 < 1 ms，给 5x 余量
        assert result["avg_ms"] < 5.0
        assert result["p95_ms"] < 10.0


@pytest.mark.slow
@pytest.mark.requires_torch
class TestForecastLatency:
    def test_forecast_under_50ms(self):
        torch = pytest.importorskip("torch")
        from services.prediction import temporal_model as tm

        # 用真实离线训过的 .pt 而不是随机初始化模型
        model = tm._load_pretrained()
        if model is None:
            pytest.skip("artifacts/temporal_model.pt 不存在")

        rows = [{
            "smoothness_score": 80.0 + (i * 0.1),
            "spacing_score": 75.0,
            "defect_type_score": 85.0,
            "total_score": 80.0,
        } for i in range(20)]

        def _once():
            tm.forecast(model, rows)

        result = _bench(_once, iterations=200)
        print(f"\n[Forecast] avg={result['avg_ms']:.3f} ms, p95={result['p95_ms']:.3f} ms")
        # 文档声称 < 10 ms，给 5x 余量
        assert result["avg_ms"] < 50.0


@pytest.mark.slow
class TestRadarAggregateLatency:
    def test_aggregate_200_records_under_50ms(self):
        from api import predict

        class FakeRecord:
            def __init__(self, i):
                self.id = i
                self.smoothness_score = 80
                self.spacing_score = 80
                self.defect_type_score = 80
                self.total_score = 80
                self.actual_width = 5.5
                self.defect_type_name = "气孔" if i % 3 == 0 else "良好焊缝"
                self.timestamp = datetime(2026, 5, 1) + timedelta(minutes=i)

        records = [FakeRecord(i) for i in range(200)]

        def _once():
            predict._aggregate_radar(list(reversed(records)))

        result = _bench(_once, iterations=200)
        print(f"\n[RadarAgg-200] avg={result['avg_ms']:.3f} ms, p95={result['p95_ms']:.3f} ms")
        assert result["avg_ms"] < 50.0


@pytest.mark.slow
class TestBoxIouThroughput:
    def test_box_iou_100k_under_200ms(self):
        from api.yolo_realtime import _box_iou

        a = [10.0, 10.0, 100.0, 100.0]
        b = [50.0, 50.0, 150.0, 150.0]

        # 100k 次 IoU 调用
        t0 = time.perf_counter()
        for _ in range(100_000):
            _box_iou(a, b)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"\n[box_iou x 100k] total={elapsed_ms:.1f} ms ({elapsed_ms / 100:.3f} μs/op)")
        # 100k 次合计 < 200 ms，对应单次 < 2 μs
        assert elapsed_ms < 200.0


@pytest.mark.slow
class TestBboxNormalizeThroughput:
    def test_normalize_500_detections_under_5ms(self):
        from api.yolo_realtime import _normalize_bboxes

        dets = []
        for i in range(500):
            dets.append({
                "box": [10 + i * 0.5, 20, 100 + i * 0.5, 90],
                "class_name": "Crack",
                "class_name_cn": "裂纹",
                "confidence": 0.7,
            })

        def _once():
            _normalize_bboxes(dets, 1920, 1080)

        result = _bench(_once, iterations=200)
        print(f"\n[normalize 500] avg={result['avg_ms']:.3f} ms")
        assert result["avg_ms"] < 5.0


@pytest.mark.slow
class TestDefectTypesLookup:
    def test_id_to_cn_lookup_throughput(self):
        from defect_types import get_defect_name_cn

        t0 = time.perf_counter()
        for _ in range(100_000):
            for i in range(17):
                get_defect_name_cn(i)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"\n[get_defect_name_cn x 1.7M] total={elapsed_ms:.1f} ms")
        # 1.7M 次查表 < 500 ms（dict lookup 量级）
        assert elapsed_ms < 500.0
