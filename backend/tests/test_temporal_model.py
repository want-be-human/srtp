"""1D-CNN 时序预测器的单元测试。

模型对外承诺三件事：
1. 输入长度 < MIN_INFER_WINDOW 时返回中性预测（不崩、不乱出值，让上游回退 RF）；
2. 同一份权重支持任意 [MIN, MAX_INFER_WINDOW] 区间长度的输入；
3. 离线训出的 .pt 能正常 load 进来，warm-start 跑通推理。

这些是 production 路径（deep 预测、warm-load）的隐含契约，跑测试比读代码确认更稳。
"""

from typing import List

import pytest

torch = pytest.importorskip("torch")
import numpy as np

from services.prediction import temporal_model as tm


def _make_rows(n: int, base: float = 75.0) -> List[dict]:
    """构造 n 条按时间升序的 fake 记录。"""
    rows = []
    for i in range(n):
        v = base + i * 0.2
        rows.append({
            "smoothness_score": v,
            "spacing_score": v - 1,
            "defect_type_score": v + 1,
            "total_score": v,
        })
    return rows


class TestForecastShape:
    def test_short_input_returns_neutral_forecast(self):
        # 不足 MIN_INFER_WINDOW=5 行，模型应该返回 5 个中性值（85.0）让上游回退
        model = tm.WeldTemporalCNN()
        model.eval()
        out = tm.forecast(model, _make_rows(3))
        assert len(out) == tm.FORECAST_SIZE
        assert all(v == 85.0 for v in out)

    @pytest.mark.parametrize("n", [5, 8, 15, 30, 60])
    def test_variable_length_input(self, n):
        # forecast 应该支持 MIN 到 MAX 任意长度，超过 MAX 自动截尾
        model = tm.WeldTemporalCNN()
        model.eval()
        out = tm.forecast(model, _make_rows(n))
        assert len(out) == tm.FORECAST_SIZE
        # 所有输出必须在 [0, 100] 区间内（np.clip 兜底）
        assert all(0.0 <= v <= 100.0 for v in out)

    def test_forecast_is_deterministic_with_same_weights(self):
        # 同一组权重 + 同一份输入应该得到完全相同的预测
        torch.manual_seed(42)
        model = tm.WeldTemporalCNN()
        model.eval()
        rows = _make_rows(10)
        out1 = tm.forecast(model, rows)
        out2 = tm.forecast(model, rows)
        assert out1 == out2


class TestRowsToArray:
    def test_dict_input(self):
        rows = [{
            "smoothness_score": 80.0,
            "spacing_score": 75.0,
            "defect_type_score": 85.0,
            "total_score": 80.0,
        }]
        arr = tm._rows_to_array(rows)
        assert arr.shape == (1, 4)
        assert arr.dtype == np.float32
        # 顺序：smoothness / width(spacing) / defect / total
        np.testing.assert_array_equal(arr[0], [80.0, 75.0, 85.0, 80.0])

    def test_none_fields_default_to_zero(self):
        rows = [{"smoothness_score": 80.0}]  # 其它三项缺失
        arr = tm._rows_to_array(rows)
        assert arr[0][0] == 80.0
        assert arr[0][1] == 0.0
        assert arr[0][2] == 0.0
        assert arr[0][3] == 0.0

    def test_orm_like_object(self):
        # ORM 行用 getattr 取值，dict 用 .get；两路都要 work
        class Row:
            smoothness_score = 70.0
            spacing_score = 65.0
            defect_type_score = 75.0
            total_score = 70.0

        arr = tm._rows_to_array([Row()])
        assert arr.shape == (1, 4)
        np.testing.assert_array_equal(arr[0], [70.0, 65.0, 75.0, 70.0])


class TestBuildBuckets:
    def test_too_few_samples_returns_empty(self):
        # 少于 min(TRAIN_WINDOWS) + FORECAST_SIZE 行就切不出任何桶
        arr = tm._rows_to_array(_make_rows(5))
        buckets = tm._build_buckets(arr)
        assert buckets == {}

    def test_enough_samples_produces_buckets(self):
        # 50 行能切出全部 5 个 window bucket
        arr = tm._rows_to_array(_make_rows(50))
        buckets = tm._build_buckets(arr)
        assert set(buckets.keys()) == set(tm.TRAIN_WINDOWS)
        # 每个 bucket 形状应为 (N, FEATURE_DIM, L) 和 (N, FORECAST_SIZE)
        for L, (X, y) in buckets.items():
            assert X.shape[1] == tm.FEATURE_DIM
            assert X.shape[2] == L
            assert y.shape[1] == tm.FORECAST_SIZE


@pytest.mark.requires_torch
class TestPretrainedWeights:
    def test_load_pretrained_or_none(self):
        # 不强制要求 .pt 存在；存在就必须能 load 成 eval 模式模型
        model = tm._load_pretrained()
        if model is None:
            pytest.skip("artifacts/temporal_model.pt 不存在，跳过")
        assert isinstance(model, tm.WeldTemporalCNN)
        assert not model.training

    def test_pretrained_forecast_produces_meaningful_values(self):
        # 用离线训过的权重对 20 行 fake 输入做预测，输出不该全 == 85（中性兜底）
        model = tm._load_pretrained()
        if model is None:
            pytest.skip("artifacts/temporal_model.pt 不存在，跳过")
        out = tm.forecast(model, _make_rows(20))
        assert len(out) == tm.FORECAST_SIZE
        # 至少有一个值不等于中性兜底 85
        assert not all(v == 85.0 for v in out)


class TestModelArchitecture:
    def test_param_count_matches_doc(self):
        # 文档声称 1349 个参数（5.3 KB），架构改了这测试就要重新对账
        model = tm.WeldTemporalCNN()
        n_params = sum(p.numel() for p in model.parameters())
        assert n_params == 1349

    def test_forward_accepts_variable_length(self):
        # 同一份权重必须能吃 5, 10, 30 等任意长度（AdaptiveAvgPool 的承诺）
        model = tm.WeldTemporalCNN()
        model.eval()
        for L in [5, 10, 17, 30]:
            x = torch.randn(1, tm.FEATURE_DIM, L)
            with torch.no_grad():
                y = model(x)
            assert y.shape == (1, tm.FORECAST_SIZE)
