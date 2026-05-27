"""预测雷达图聚合逻辑的纯函数测试。

`_aggregate_radar` 是雷达图所有 6 维的唯一来源（前端 PK / 学生对比 / AI 雷达都靠它），
必须保证：
1. 输入空记录返回零向量，不抛 ZeroDivisionError；
2. 6 维都在 [0, 100] 区间内；
3. 进步速率：递增序列 > 50，递减序列 < 50；
4. 宽度准度：actual_width 都等于 OPTIMAL 时给 100；
5. 缺陷集中度：单一缺陷给 ~85.7（=100-1/7*100），多样化给低分。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# 让 backend/ 进入 sys.path，再 import api.predict
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from api import predict


class FakeRecord:
    """模拟 SQLAlchemy ORM 记录，避免起 DB 也能跑纯逻辑测试。

    `_aggregate_radar` 入参是 timestamp.desc() 排序的 list（最新在前），
    用 idx 反映构造顺序，便于断言前段/后段。
    """

    def __init__(self, idx: int,
                 smoothness: float = 80, spacing: float = 80,
                 defect: float = 80, total: float = 80,
                 actual_width: float = 5.5,
                 defect_type_name: str = "良好焊缝"):
        self.id = idx
        self.smoothness_score = smoothness
        self.spacing_score = spacing
        self.defect_type_score = defect
        self.total_score = total
        self.actual_width = actual_width
        self.defect_type_name = defect_type_name
        self.timestamp = datetime(2026, 5, 1) + timedelta(minutes=idx)


def _records_desc(rows: list[FakeRecord]) -> list[FakeRecord]:
    """模仿 query.order_by(timestamp.desc()) 给的顺序：最新在前。"""
    return list(reversed(rows))


class TestEmptyInput:
    def test_no_records_returns_zero_vectors(self):
        defect_radar, counts, skill_radar, n = predict._aggregate_radar([])
        assert n == 0
        assert all(v == 0.0 for v in defect_radar.values())
        assert all(v == 0 for v in skill_radar.values())


class TestSkillRadarBounds:
    def test_six_dimensions_present(self):
        rows = [FakeRecord(i) for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert set(skill.keys()) == set(predict.SKILL_RADAR_AXES)

    def test_all_values_in_0_100(self):
        rows = [FakeRecord(i, smoothness=85, spacing=80, defect=90, total=85,
                           actual_width=5.5) for i in range(20)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        for k, v in skill.items():
            assert 0.0 <= v <= 100.0, f"{k}={v} 超出 [0,100]"


class TestProgressRate:
    def test_increasing_series_gives_high_progress(self):
        # 总分从 60 单调升到 90，应给 > 50 的进步速率
        rows = [FakeRecord(i, total=60 + i * 1.5) for i in range(20)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["进步速率"] > 50.0

    def test_decreasing_series_gives_low_progress(self):
        # 单调下降，进步速率应 < 50
        rows = [FakeRecord(i, total=90 - i * 1.5) for i in range(20)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["进步速率"] < 50.0

    def test_flat_series_around_50(self):
        # 完全平稳，进步速率应在 50 附近（噪声为 0 时严格 == 50）
        rows = [FakeRecord(i, total=80) for i in range(20)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["进步速率"] == pytest.approx(50.0, abs=0.5)

    def test_too_few_records_defaults_to_50(self):
        # n < 4 时进步速率走默认 50，不能算除零
        rows = [FakeRecord(i, total=80) for i in range(3)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["进步速率"] == 50.0


class TestWidthAccuracy:
    def test_all_optimal_width_gives_100(self):
        from config import OPTIMAL_WELD_WIDTH_MM
        rows = [FakeRecord(i, actual_width=OPTIMAL_WELD_WIDTH_MM) for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["宽度准度"] == pytest.approx(100.0, abs=0.01)

    def test_off_optimal_width_loses_points(self):
        from config import OPTIMAL_WELD_WIDTH_MM
        # 偏 1mm，倍数 ×10 扣 10 分 → 90
        rows = [FakeRecord(i, actual_width=OPTIMAL_WELD_WIDTH_MM + 1.0) for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["宽度准度"] == pytest.approx(90.0, abs=0.01)

    def test_extreme_off_width_clamps_to_0(self):
        # 偏 50mm 应被 clamp 到 0，不能出负数
        rows = [FakeRecord(i, actual_width=100.0) for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["宽度准度"] == 0.0

    def test_no_width_data_returns_zero(self):
        rows = [FakeRecord(i, actual_width=None) for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["宽度准度"] == 0.0


class TestDefectFocus:
    def test_single_defect_type_high_focus(self):
        # 唯一缺陷类型 → distinct=1 → 100 - 1/7*100 ≈ 85.7
        rows = [FakeRecord(i, defect_type_name="气孔") for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["缺陷集中度"] == pytest.approx(85.71, abs=0.1)

    def test_diverse_defects_lower_focus(self):
        # 7 种不同缺陷 → distinct=7 → 100 - 7/7*100 = 0
        types = ["气孔", "夹渣", "未熔合", "焊瘤", "咬边", "裂纹", "焊穿"]
        rows = [FakeRecord(i, defect_type_name=types[i % 7]) for i in range(7)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["缺陷集中度"] == pytest.approx(0.0, abs=0.01)

    def test_good_weld_does_not_count(self):
        # 全部"良好焊缝"应该被 NON_DEFECT_LABELS 过滤掉，distinct=0 → 100
        rows = [FakeRecord(i, defect_type_name="良好焊缝") for i in range(10)]
        _, _, skill, _ = predict._aggregate_radar(_records_desc(rows))
        assert skill["缺陷集中度"] == 100.0


class TestDefectRadar:
    def test_six_axes_match_radar_defect_types(self):
        from defect_types import RADAR_DEFECT_TYPES
        assert set(predict.DEFECT_RADAR_AXES) == set(RADAR_DEFECT_TYPES)

    def test_distribution_normalizes_to_100_percent(self):
        # 缺陷比例之和应严格 = 100（counts > 0 时）
        # 标签从 best.pt 6 类里挑，"夹渣 / 未熔合" 现在不在模型词表里
        rows = [
            FakeRecord(0, defect_type_name="气孔"),
            FakeRecord(1, defect_type_name="气孔"),
            FakeRecord(2, defect_type_name="飞溅"),
            FakeRecord(3, defect_type_name="裂纹"),
        ]
        defect_radar, counts, _, _ = predict._aggregate_radar(_records_desc(rows))
        assert sum(defect_radar.values()) == pytest.approx(100.0, abs=0.1)
        assert counts["气孔"] == 2
        assert counts["飞溅"] == 1


class TestSummaryText:
    def test_zero_records_message(self):
        skill = {k: 0 for k in predict.SKILL_RADAR_AXES}
        counts = {k: 0 for k in predict.DEFECT_RADAR_AXES}
        text = predict._summary_text(skill, counts, 0, "我的")
        assert "尚无检测记录" in text

    def test_no_defects_message(self):
        skill = {k: 80 for k in predict.SKILL_RADAR_AXES}
        counts = {k: 0 for k in predict.DEFECT_RADAR_AXES}
        text = predict._summary_text(skill, counts, 10, "我的")
        assert "未观察到典型缺陷" in text

    def test_defects_message_picks_top(self):
        skill = {k: 80 for k in predict.SKILL_RADAR_AXES}
        skill["缺陷控制"] = 60  # 故意把缺陷控制设为最弱
        counts = {k: 0 for k in predict.DEFECT_RADAR_AXES}
        counts["气孔"] = 5
        counts["飞溅"] = 2
        text = predict._summary_text(skill, counts, 10, "我的")
        assert "气孔" in text  # 最频发
        assert "5" in text     # 次数
        assert "缺陷控制" in text  # 最弱维度
